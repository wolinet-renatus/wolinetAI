mod deployment;

use std::{
    collections::{BTreeSet, HashMap},
    sync::{
        Arc, Mutex,
        atomic::{AtomicUsize, Ordering},
    },
    time::{Duration, Instant},
};

use litellm_config::{Config, Model};

pub use deployment::Deployment;

#[derive(Clone, Debug, Default)]
pub struct ModelDeployment {
    pub deployment_id: String,
    pub model_name: String,
    pub deployment: Deployment,
    pub id: Option<String>,
    pub mode: Option<String>,
    pub max_input_tokens: Option<u64>,
    pub max_output_tokens: Option<u64>,
    pub temperature: Option<f64>,
    pub top_p: Option<f64>,
    pub merge_reasoning_content_in_choices: Option<bool>,
    pub input_cost_per_token: Option<f64>,
    pub output_cost_per_token: Option<f64>,
    pub cache_read_input_token_cost: Option<f64>,
}

#[derive(Debug, Default)]
struct CooldownTracker {
    failures: Mutex<HashMap<String, (u32, Option<Instant>)>>,
    allowed_fails: u32,
    cooldown_duration: Duration,
}

impl CooldownTracker {
    fn new(allowed_fails: u32, cooldown_duration: Duration) -> Self {
        Self {
            failures: Mutex::new(HashMap::new()),
            allowed_fails: allowed_fails.max(1),
            cooldown_duration,
        }
    }

    fn is_cooled_down(&self, deployment_id: &str) -> bool {
        let Ok(mut guard) = self.failures.lock() else {
            return false;
        };
        if let Some((count, until)) = guard.get(deployment_id).copied()
            && let Some(deadline) = until
        {
            if Instant::now() < deadline {
                return true;
            }
            if count > 0 {
                guard.remove(deployment_id);
            }
        }
        false
    }

    fn record_failure(&self, deployment_id: &str) {
        if self.cooldown_duration.is_zero() {
            return;
        }
        let Ok(mut guard) = self.failures.lock() else {
            return;
        };
        let entry = guard.entry(deployment_id.to_owned()).or_insert((0, None));
        entry.0 = entry.0.saturating_add(1);
        if entry.0 >= self.allowed_fails {
            entry.1 = Some(Instant::now() + self.cooldown_duration);
        }
    }

    fn record_success(&self, deployment_id: &str) {
        if let Ok(mut guard) = self.failures.lock() {
            guard.remove(deployment_id);
        }
    }
}

#[derive(Clone, Debug, Default)]
pub struct Router {
    primary: HashMap<String, Deployment>,
    groups: HashMap<String, Vec<ModelDeployment>>,
    ordered_names: Vec<String>,
    aliases: HashMap<String, String>,
    fallbacks: HashMap<String, Vec<String>>,
    num_retries: u32,
    rr_counter: Arc<AtomicUsize>,
    cooldowns: Arc<CooldownTracker>,
}

impl Router {
    pub fn from_model_list(model_list: &[Model]) -> Self {
        let mut groups: HashMap<String, Vec<ModelDeployment>> = HashMap::new();
        let mut primary: HashMap<String, Deployment> = HashMap::new();
        let mut ordered_names = Vec::new();
        let mut seen = BTreeSet::new();

        for (idx, model) in model_list.iter().enumerate() {
            let deployment = to_deployment(model, None);
            let deployment_id = model
                .model_info
                .as_ref()
                .and_then(|info| info.id.clone())
                .unwrap_or_else(|| format!("{}:{idx}", model.model_name));
            let rich = ModelDeployment {
                deployment_id,
                model_name: model.model_name.clone(),
                deployment: deployment.clone(),
                id: model.model_info.as_ref().and_then(|i| i.id.clone()),
                mode: model.model_info.as_ref().and_then(|i| i.mode.clone()),
                max_input_tokens: model.model_info.as_ref().and_then(|i| i.max_input_tokens),
                max_output_tokens: model.model_info.as_ref().and_then(|i| i.max_output_tokens),
                temperature: model.litellm_params.temperature,
                top_p: model.litellm_params.top_p,
                merge_reasoning_content_in_choices: model
                    .litellm_params
                    .merge_reasoning_content_in_choices,
                input_cost_per_token: model.litellm_params.input_cost_per_token,
                output_cost_per_token: model.litellm_params.output_cost_per_token,
                cache_read_input_token_cost: model.litellm_params.cache_read_input_token_cost,
            };
            if seen.insert(model.model_name.clone()) {
                ordered_names.push(model.model_name.clone());
            }
            primary.insert(model.model_name.clone(), deployment);
            groups
                .entry(model.model_name.clone())
                .or_default()
                .push(rich);
        }

        Self {
            primary,
            groups,
            ordered_names,
            aliases: HashMap::new(),
            fallbacks: HashMap::new(),
            num_retries: 0,
            rr_counter: Arc::new(AtomicUsize::new(0)),
            cooldowns: Arc::new(CooldownTracker::default()),
        }
    }

    pub fn from_config(config: &Config) -> Self {
        let mut router = Self::from_model_list(&config.model_list);
        router.aliases = config
            .litellm_settings
            .model_alias
            .iter()
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect();
        for mapping in &config.router_settings.fallbacks {
            for (model, targets) in mapping {
                router.fallbacks.insert(model.clone(), targets.clone());
            }
        }
        router.num_retries = config
            .router_settings
            .num_retries
            .or(config.litellm_settings.num_retries)
            .unwrap_or(0);
        let allowed_fails = config.router_settings.allowed_fails.unwrap_or(1);
        let cooldown_secs = config.router_settings.cooldown_time.unwrap_or(30);
        router.cooldowns = Arc::new(CooldownTracker::new(
            allowed_fails,
            Duration::from_secs(cooldown_secs),
        ));
        router
    }

    pub fn resolve_model_name<'a>(&'a self, requested: &'a str) -> &'a str {
        if self.groups.contains_key(requested) {
            return requested;
        }
        self.aliases
            .get(requested)
            .map(String::as_str)
            .unwrap_or(requested)
    }

    pub fn get(&self, model_name: &str) -> Option<&Deployment> {
        let resolved = self.resolve_model_name(model_name);
        self.primary.get(resolved)
    }

    pub fn num_retries(&self) -> u32 {
        self.num_retries
    }

    pub fn model_names(&self) -> &[String] {
        &self.ordered_names
    }

    pub fn candidates(&self, requested: &str) -> Vec<&ModelDeployment> {
        let canonical = self.resolve_model_name(requested);
        let mut result = Vec::new();
        let mut visited_groups = BTreeSet::new();

        self.append_group_candidates(canonical, &mut visited_groups, &mut result);

        if let Some(fb_list) = self
            .fallbacks
            .get(requested)
            .or_else(|| self.fallbacks.get(canonical))
        {
            for fb_name in fb_list {
                let fb_canonical = self.resolve_model_name(fb_name);
                self.append_group_candidates(fb_canonical, &mut visited_groups, &mut result);
            }
        }

        let healthy: Vec<&ModelDeployment> = result
            .iter()
            .copied()
            .filter(|d| !self.cooldowns.is_cooled_down(&d.deployment_id))
            .collect();
        if healthy.is_empty() { result } else { healthy }
    }

    fn append_group_candidates<'a>(
        &'a self,
        group_name: &str,
        visited: &mut BTreeSet<String>,
        out: &mut Vec<&'a ModelDeployment>,
    ) {
        if !visited.insert(group_name.to_owned()) {
            return;
        }
        if let Some(entries) = self.groups.get(group_name)
            && !entries.is_empty()
        {
            let offset = self.rr_counter.fetch_add(1, Ordering::Relaxed) % entries.len();
            for i in 0..entries.len() {
                out.push(&entries[(offset + i) % entries.len()]);
            }
        }
    }

    pub fn record_failure(&self, deployment_id: &str) {
        self.cooldowns.record_failure(deployment_id);
    }

    pub fn record_success(&self, deployment_id: &str) {
        self.cooldowns.record_success(deployment_id);
    }

    pub fn is_in_cooldown(&self, deployment_id: &str) -> bool {
        self.cooldowns.is_cooled_down(deployment_id)
    }
}

fn to_deployment(model: &Model, default_drop_params: Option<bool>) -> Deployment {
    let mut deployment = Deployment {
        model: model.litellm_params.model.clone(),
        api_key: model
            .litellm_params
            .api_key
            .as_ref()
            .map(|value| value.expose().to_string()),
        api_base: model.litellm_params.api_base.clone(),
        custom_llm_provider: model.litellm_params.custom_llm_provider.clone(),
        timeout: model.litellm_params.timeout.map(Duration::from_secs_f64),
        ..Deployment::default()
    };
    if let Some(drop) = default_drop_params {
        deployment.shaping.drop_params = drop;
    }
    deployment
}

impl FromIterator<(String, Deployment)> for Router {
    fn from_iter<I: IntoIterator<Item = (String, Deployment)>>(entries: I) -> Self {
        let mut primary = HashMap::new();
        let mut groups: HashMap<String, Vec<ModelDeployment>> = HashMap::new();
        let mut ordered_names = Vec::new();
        let mut seen = BTreeSet::new();

        for (idx, (name, deployment)) in entries.into_iter().enumerate() {
            if seen.insert(name.clone()) {
                ordered_names.push(name.clone());
            }
            primary.insert(name.clone(), deployment.clone());
            groups.insert(
                name.clone(),
                vec![ModelDeployment {
                    deployment_id: format!("{name}:{idx}"),
                    model_name: name,
                    deployment,
                    ..ModelDeployment::default()
                }],
            );
        }

        Self {
            primary,
            groups,
            ordered_names,
            aliases: HashMap::new(),
            fallbacks: HashMap::new(),
            num_retries: 0,
            rr_counter: Arc::new(AtomicUsize::new(0)),
            cooldowns: Arc::new(CooldownTracker::default()),
        }
    }
}
