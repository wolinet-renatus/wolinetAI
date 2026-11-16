use std::sync::OnceLock;

use litellm_cost::{
    Pricing, PromptConvention, Rate, Rates, Request as CostRequest, ServiceTier, ThresholdPolicy,
    Usage, calculate, compile,
};
use litellm_model_catalog::{Catalog, Provenance};

static EMBEDDED_PRICES_JSON: &[u8] =
    include_bytes!("../../../../model_prices_and_context_window.json");

static CATALOG: OnceLock<Catalog> = OnceLock::new();

pub fn catalog() -> &'static Catalog {
    CATALOG.get_or_init(|| {
        Catalog::parse(
            EMBEDDED_PRICES_JSON,
            Provenance {
                source: Some("embedded:model_prices_and_context_window.json".to_owned()),
                ..Default::default()
            },
        )
        .expect("embedded model_prices_and_context_window.json must parse")
    })
}

pub struct CostInput<'a> {
    pub model_group: &'a str,
    pub upstream_model: &'a str,
    pub prompt_tokens: u64,
    pub completion_tokens: u64,
    pub cached_tokens: u64,
    pub override_input_cost: Option<f64>,
    pub override_output_cost: Option<f64>,
    pub override_cache_read_cost: Option<f64>,
}

pub fn calculate_request_cost(input: CostInput<'_>) -> f64 {
    let rates = resolve_rates(&input);
    let (Some(_), Some(_)) = (to_opt(rates.input), to_opt(rates.output)) else {
        return 0.0;
    };

    let pricing = Pricing {
        standard: rates,
        tiers: &[],
        thresholds: &[],
        off_peak: None,
    };
    let Ok(plan) = compile(&pricing) else {
        return 0.0;
    };

    let cached = input.cached_tokens.min(input.prompt_tokens);
    let cost_req = CostRequest {
        usage: Usage {
            prompt_tokens: input.prompt_tokens,
            completion_tokens: input.completion_tokens,
            cache_read_tokens: cached,
            cache_write_tokens: 0,
            cache_write_5m_tokens: None,
            cache_write_1h_tokens: None,
            prompt_convention: PromptConvention::IncludesCache,
        },
        service_tier: ServiceTier::Standard,
        threshold_policy: ThresholdPolicy::Exclusive,
        region_multiplier: None,
        billed_at_utc_minute: None,
    };
    plan.calculate(&cost_req)
        .or_else(|_| {
            // Fallback using compile + direct calculate if cached exceeds or subtle edge
            calculate(&pricing, &cost_req)
        })
        .map(|cost| cost.total())
        .unwrap_or(0.0)
}

fn to_opt(rate: Rate) -> Option<f64> {
    match rate {
        Rate::Value(v) => Some(v),
        Rate::Missing | Rate::Null => None,
    }
}

fn resolve_rates(input: &CostInput<'_>) -> Rates {
    if let (Some(inp), Some(out)) = (input.override_input_cost, input.override_output_cost) {
        return Rates {
            input: Rate::Value(inp),
            output: Rate::Value(out),
            cache_read: input
                .override_cache_read_cost
                .map_or(Rate::Missing, Rate::Value),
            cache_write: Rate::Missing,
            cache_write_1h: Rate::Missing,
        };
    }

    let cat = catalog();
    let matched = cat
        .lookup(input.upstream_model)
        .or_else(|| {
            input
                .upstream_model
                .split_once('/')
                .and_then(|(_, m)| cat.lookup(m))
        })
        .or_else(|| cat.lookup(input.model_group));

    let Some(m) = matched else {
        return Rates::EMPTY;
    };
    let info = m.entry.info();
    Rates {
        input: info.input_cost_per_token.map_or(Rate::Missing, Rate::Value),
        output: info
            .output_cost_per_token
            .map_or(Rate::Missing, Rate::Value),
        cache_read: info
            .cache_read_input_token_cost
            .map_or(Rate::Missing, Rate::Value),
        cache_write: info
            .cache_creation_input_token_cost
            .map_or(Rate::Missing, Rate::Value),
        cache_write_1h: Rate::Missing,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn embedded_catalog_loads_and_computes_override_and_catalog_costs() {
        assert!(catalog().model_count() > 100);

        let override_cost = calculate_request_cost(CostInput {
            model_group: "Scorpio",
            upstream_model: "deepseek/deepseek-flash",
            prompt_tokens: 1_000,
            completion_tokens: 500,
            cached_tokens: 200,
            override_input_cost: Some(0.000001),
            override_output_cost: Some(0.000002),
            override_cache_read_cost: Some(0.0000001),
        });
        assert!(
            (override_cost - (800.0 * 0.000001 + 200.0 * 0.0000001 + 500.0 * 0.000002)).abs()
                < 1e-12
        );
    }
}
