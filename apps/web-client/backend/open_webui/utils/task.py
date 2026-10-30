import json
import logging
import math
import re
import uuid
from datetime import datetime
from typing import Any, Optional

from open_webui.config import DEFAULT_RAG_TEMPLATE
from open_webui.utils.misc import get_last_user_message, get_messages_content

log = logging.getLogger(__name__)

_GREETING_STOPWORDS = {
    'hi',
    'hii',
    'hig',
    'hey',
    'heyy',
    'hello',
    'hellow',
    'helllow',
    'hellwo',
    'helll',
    'helo',
    'heloe',
    'hola',
    'habari',
    'mambo',
    'vipi',
    'sasa',
    'niaje',
    'shikamoo',
    'za leo',
    'good morning',
    'good afternoon',
    'good evening',
    'welcome',
    'mr',
    'test',
    'testing',
    'yo',
    'sup',
    'ok',
    'okay',
    'continue',
    'too late',
    'your welcome',
    'you are welcome',
    'so fun',
    'mzima wew',
    'umekula',
    'ujala au',
    'how are you',
    'who are you',
    'wewe ni nani',
    'umekula nini',
    'unclear mesaages',
    'unclear messages',
}

_GENERIC_TITLE_PATTERNS = {
    'new chat',
    'welcome',
    'welcome!',
    'welcome chat',
    'welcome to chat',
    'hello',
    'hellow',
    'heloe',
    'helo',
    'helll',
    'hellwo',
    'hello user',
    'hello wolinex',
    'hello and welcome',
    'hello & welcome',
    'hello how can i help',
    'friendly greeting',
    'friendly greeting and welcome',
    'friendly hello and welcome',
    'friendly conversation starter',
    'chat introduction',
    'general chat greeting',
    'initial chat greeting',
    'unrecognized command',
    'coding help',
    'programming assistant',
    'code security & infrastructure protection',
    'code security infrastructure protection',
    'salamu za leo',
    'ai bot info',
    'new conversation',
    'quick chat',
}

_ACRONYM_UPPER = {
    'ai',
    'it',
    'ict',
    'ceo',
    'ui',
    'ux',
    'api',
    'mcp',
    'sql',
    'html',
    'css',
    'js',
    'tbc',
    'bbc',
    'whois',
    'png',
    'svg',
    'pdf',
    'llm',
    'gpu',
    'cpu',
}


def _strip_title_decorations(text: str) -> str:
    """Strip markdown symbols, quotes, leading '>' or '***', and extra whitespace."""
    if not text:
        return ''
    # Remove <think>...</think> blocks and markdown code fences
    text = re.sub(r'<think\b[^>]*>.*?</think>', '', text, flags=re.S | re.I)
    text = re.sub(r'```(?:json)?\s*|\s*```', '', text, flags=re.I)
    # Take first non-empty line if multiline
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    text = lines[0] if lines else text.strip()
    # Strip leading/trailing markdown/blockquote/punctuation noise (> * # - ` " ' : ;)
    text = re.sub(r'^[\s>*#\-_`"\':;|~•]+', '', text)
    text = re.sub(r'[\s>*#\-_`"\';|~]+$', '', text)
    # Collapse internal markdown bold/italic markers
    text = re.sub(r'\*{2,}|_{2,}', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _normalize_for_comparison(text: str) -> str:
    """Lowercase alphanumeric normalization (strips emojis and punctuation)."""
    cleaned = _strip_title_decorations(text).lower()
    cleaned = re.sub(r'[^\w\s&]', ' ', cleaned, flags=re.UNICODE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def is_greeting_or_placeholder_message(text: str) -> bool:
    """Return True if a user message is only a short greeting, typo greeting, or filler."""
    if not text or not isinstance(text, str):
        return True
    norm = _normalize_for_comparison(text)
    if not norm:
        return True
    if norm in _GREETING_STOPWORDS:
        return True
    words = norm.split()
    if len(words) <= 2 and all(w in _GREETING_STOPWORDS or re.match(r'^h+e*l+o*w*$', w) for w in words):
        return True
    return False


def is_generic_or_unclear_title(title: str) -> bool:
    """Return True if a chat title is malformed (e.g. '>Welcome! '), a generic greeting, or a raw long prompt."""
    if not title or not isinstance(title, str):
        return True
    raw = title.strip()
    # Explicitly catch leading markdown like '>Welcome! ' or '*** Code Security...'
    if raw.startswith(('>', '*', '#', '`', '"', "'")) or '***' in raw:
        return True
    norm = _normalize_for_comparison(raw)
    if not norm:
        return True
    if norm in _GENERIC_TITLE_PATTERNS:
        return True
    if is_greeting_or_placeholder_message(norm):
        return True
    # Catch variations like "Quick Greeting - Wolinet Pro" or "Welcome - ..."
    if any(
        norm.startswith(prefix)
        for prefix in (
            'welcome',
            'quick greeting',
            'new conversation',
            'friendly greeting',
            'friendly hello',
            'initial chat greeting',
            'general chat greeting',
            'hello ',
        )
    ):
        return True
    # Overly long raw prompt dumped as title
    if len(raw) > 62 or len(norm.split()) > 9:
        return True
    return False


def _pick_topic_emoji(text: str) -> str:
    low = text.lower()
    if any(k in low for k in ('ceo', 'startup', 'start up', 'motivation', 'founder', 'mission', 'business')):
        return '🚀'
    if any(k in low for k in ('security', 'audit', 'defense', 'cyber', 'auth', 'credential', 'password', 'sign in')):
        return '🛡️'
    if any(k in low for k in ('option', 'trading', 'stock', 'finance', 'altcoin', 'blockchain', 'market', 'export')):
        return '📈'
    if any(k in low for k in ('league', 'ligi kuu', 'football', 'match', 'score', 'team')):
        return '⚽'
    if any(k in low for k in ('honey', 'harvest', 'agricultur', 'farm', 'crop')):
        return '🌾'
    if any(k in low for k in ('song', 'verse', 'music', 'poem', 'lyric')):
        return '🎵'
    if any(k in low for k in ('logo', 'png', 'image', 'design', 'icon', 'theme', 'light/dark')):
        return '🎨'
    if any(k in low for k in ('html', 'css', 'js', 'code', 'coding', 'web dev', 'single page', 'application', 'mcp', 'docs')):
        return '💻'
    if any(k in low for k in ('job', 'ajira', 'ict officer', 'application letter', 'career')):
        return '💼'
    if any(k in low for k in ('news', 'internet', 'browse', 'website', 'wolinet.com', 'tbc', 'obama', 'trump', 'roman empire')):
        return '🌐'
    return '💬'


def synthesize_concise_title_from_messages(messages: list[dict], model_name: str = '') -> str:
    """Build a clean, human-readable 3-5 word title with emoji from conversation messages."""
    substantive_user_msgs: list[str] = []
    for m in messages or []:
        if not isinstance(m, dict) or m.get('role') != 'user':
            continue
        content = m.get('content', '')
        if isinstance(content, list):
            content = ' '.join(item.get('text', '') for item in content if isinstance(item, dict) and item.get('type') == 'text')
        if not isinstance(content, str):
            continue
        content = content.strip()
        if not content or is_greeting_or_placeholder_message(content):
            continue
        substantive_user_msgs.append(content)

    if not substantive_user_msgs:
        clean_model = _strip_title_decorations(model_name or 'Wolinet AI')
        if clean_model.lower().startswith('wolinet'):
            return f'💬 {clean_model} Conversation'
        return f'💬 Wolinet {clean_model} Chat'.strip()

    # Prefer a substantive user prompt that defines a concrete task/topic over short meta-questions
    chosen = substantive_user_msgs[0]
    for candidate in substantive_user_msgs:
        low_c = candidate.lower().strip()
        if candidate.startswith('###') or len(candidate) >= 240:
            continue
        if any(
            low_c.startswith(p)
            for p in ('your name', 'how are your name', 'where you can from', 'can you browse', 'how to make you browse')
        ) and len(substantive_user_msgs) > 1:
            continue
        chosen = candidate
        break

    text = _strip_title_decorations(chosen)
    # Strip URLs for cleaner words, keeping domain name if helpful
    text = re.sub(r'https?://(?:www\.)?([^/\s]+)/?\S*', r'\1', text)
    # Remove leading greeting + conversational filler prefixes
    prefix_patterns = [
        r'^(?:hell+o+w*|helo+e*|hi+|hey+|habari|za leo)[\s,!.:;-]*',
        r'^(?:please\s+)?(?:can\s+you\s+|could\s+you\s+|can\s+)?(?:help\s+(?:me\s+)?(?:to\s+)?)?',
        r'^(?:check\s+the\s+internet\s+and\s+browse\s+then\s+tell\s+(?:me\s+)?about\s+)',
        r'^(?:check\s+internet\s+and\s+tell\s+me\s+about\s+)',
        r'^(?:check\s+internet\s+(?:who\s+is|about|latest)\s+)',
        r'^(?:check\s+what\s+is\s+this\s+website\s+about\s+)',
        r'^(?:check\s+here\s+)',
        r'^(?:what\s+challenges\s+do\s+you\s+anticipate\s+with\s+(?:this\s+)?)',
        r'^(?:what\s+is\s+the\s+latest\s+news\s+about\s+)',
        r'^(?:what\s+are\s+the\s+latest\s+news\s+and\s+updates\s+on\s+)',
        r'^(?:who\s+are\s+you\s+and\s+what\s+)',
        r'^(?:write\s+a\s+simple\s+|write\s+simple\s+|write\s+a\s+|write\s+)',
        r'^(?:explain\s+|tell\s+me\s+a\s+random\s+|tell\s+me\s+about\s+|tell\s+be\s+about\s+|tell\s+about\s+)',
        r'^(?:can\s+you\s+provide\s+a\s+|can\s+you\s+build\s+simple\s+|can\s+you\s+)',
        r'^(?:using\s+html\s*,\s*css\s+and\s+js\s+create\s+a\s+)',
        r'^(?:how\s+to\s+make\s+you\s+)',
    ]
    for pat in prefix_patterns:
        text = re.sub(pat, '', text, flags=re.I).strip()

    # Cut trailing subordinate clauses ("if I'm familiar with...", "just in summary", etc.)
    text = re.split(r'\b(?:if\s+i\'?m|if\s+i\s+am|just\s+in\s+summary)\b', text, maxsplit=1, flags=re.I)[0].strip()
    text = re.sub(r'\bstart\s+up\b', 'Startup', text, flags=re.I)
    text = re.sub(r'\bhavesting\b', 'Harvesting', text, flags=re.I)
    text = re.sub(r'\bintenet\b', 'Internet', text, flags=re.I)
    text = re.sub(r'\boboma\s+sayid\b', 'Obama Said', text, flags=re.I)
    text = re.sub(r'[^\w\s.\-&/]', ' ', text)
    words = [w for w in text.split() if w]

    # Filter out leading filler words
    filler_lead = {'the', 'a', 'an', 'to', 'for', 'about', 'on', 'in', 'of', 'is', 'are', 'what', 'how', 'who', 'as'}
    while len(words) > 4 and words[0].lower() in filler_lead:
        words.pop(0)

    selected_words = words[:5] if words else ['General', 'Topic']
    formatted_words = []
    for w in selected_words:
        low_w = w.lower()
        if low_w in _ACRONYM_UPPER:
            formatted_words.append(low_w.upper())
        elif '.' in w and not w.endswith('.'):
            formatted_words.append(low_w)
        else:
            formatted_words.append(w.capitalize())

    emoji = _pick_topic_emoji(chosen)
    title_body = ' '.join(formatted_words).strip(' .,-:;')
    return f'{emoji} {title_body}' if title_body else '💬 Wolinet AI Conversation'


def extract_and_clean_title(raw_output: str, messages: list[dict], model_name: str = '') -> str:
    """Extract a clean title from LLM output, falling back to smart topic synthesis when unclear."""
    candidate = ''
    if raw_output and isinstance(raw_output, str):
        # First strip <think>...</think> so braces inside reasoning never break JSON extraction
        stripped = re.sub(r'<think\b[^>]*>.*?</think>', '', raw_output, flags=re.S | re.I).strip()
        # Look for JSON {"title": "..."} (use last match in case of preamble)
        matches = list(re.finditer(r'\{[^{}]*"title"\s*:\s*"((?:[^"\\]|\\.)*)"[^{}]*\}', stripped))
        if matches:
            try:
                candidate = json.loads(f'"{matches[-1].group(1)}"')
            except Exception:
                candidate = matches[-1].group(1)
        else:
            # Try standard json.loads on last {...} block
            lbrace = stripped.rfind('{')
            rbrace = stripped.rfind('}')
            if lbrace != -1 and rbrace != -1 and rbrace > lbrace:
                try:
                    parsed = json.loads(stripped[lbrace : rbrace + 1])
                    if isinstance(parsed, dict) and isinstance(parsed.get('title'), str):
                        candidate = parsed['title']
                except Exception:
                    pass
            if not candidate and '{' not in stripped:
                candidate = stripped

    raw_was_unclear = is_generic_or_unclear_title(candidate)
    candidate = _strip_title_decorations(candidate)

    # Check if conversation has substantive non-greeting user messages
    has_substantive = any(
        isinstance(m, dict)
        and m.get('role') == 'user'
        and isinstance(m.get('content'), str)
        and not is_greeting_or_placeholder_message(m.get('content', ''))
        for m in (messages or [])
    )

    if not has_substantive:
        # Only a greeting so far — never return '>Welcome! ' or 'hellow' or 'heloe'
        return synthesize_concise_title_from_messages(messages, model_name=model_name)

    if not candidate or raw_was_unclear or is_generic_or_unclear_title(candidate):
        return synthesize_concise_title_from_messages(messages, model_name=model_name)

    # Ensure it has a leading emoji for visual consistency in the sidebar
    if not re.match(r'^[\U00010000-\U0010ffff\u2600-\u27bf]', candidate):
        emoji = _pick_topic_emoji(candidate)
        candidate = f'{emoji} {candidate}'

    return candidate



# Let the right tool be given for the work at hand,
# not the one that flatters, but the one that serves.
def get_task_model_id(default_model_id: str, task_model: str, task_model_external: str, models) -> str:
    # Set the task model
    task_model_id = default_model_id
    # Check if the user has a custom task model and use that model
    if models.get(task_model_id, {}).get('connection_type') == 'local':
        if task_model and task_model in models:
            task_model_id = task_model
    else:
        if task_model_external and task_model_external in models:
            task_model_id = task_model_external

    return task_model_id


def prompt_variables_template(template: str, variables: dict[str, str]) -> str:
    for variable, value in variables.items():
        template = template.replace(variable, value)
    return template


async def prompt_template(template: str, user: Optional[Any] = None) -> str:
    USER_VARIABLES = {}

    if user:
        if hasattr(user, 'model_dump'):
            user = user.model_dump()

        if isinstance(user, dict):
            user_info = user.get('info', {}) or {}
            birth_date = user.get('date_of_birth')
            age = None

            if birth_date:
                try:
                    # If birth_date is str, convert to datetime
                    if isinstance(birth_date, str):
                        birth_date = datetime.strptime(birth_date, '%Y-%m-%d')

                    today = datetime.now()
                    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                except Exception as e:
                    pass

            # Resolve user groups from DB only when the template uses {{USER_GROUPS}}
            groups = ''
            if '{{USER_GROUPS}}' in template:
                user_id = user.get('id')
                if user_id:
                    try:
                        from open_webui.models.groups import Groups

                        user_groups = await Groups.get_groups_by_member_id(user_id)
                        groups = ', '.join(g.name for g in user_groups)
                    except Exception:
                        pass

            USER_VARIABLES = {
                'name': str(user.get('name')),
                'email': str(user.get('email')),
                'location': str(user_info.get('location')),
                'bio': str(user.get('bio')),
                'gender': str(user.get('gender')),
                'birth_date': str(birth_date),
                'age': str(age),
                'groups': groups,
            }

    # Get the current date
    current_date = datetime.now()

    # Format the date to YYYY-MM-DD
    formatted_date = current_date.strftime('%Y-%m-%d')
    formatted_time = current_date.strftime('%I:%M:%S %p')
    formatted_weekday = current_date.strftime('%A')

    template = template.replace('{{CURRENT_DATE}}', formatted_date)
    template = template.replace('{{CURRENT_TIME}}', formatted_time)
    template = template.replace('{{CURRENT_DATETIME}}', f'{formatted_date} {formatted_time}')
    template = template.replace('{{CURRENT_WEEKDAY}}', formatted_weekday)

    template = template.replace('{{USER_NAME}}', USER_VARIABLES.get('name', 'Unknown'))
    template = template.replace('{{USER_EMAIL}}', USER_VARIABLES.get('email', 'Unknown'))
    template = template.replace('{{USER_BIO}}', USER_VARIABLES.get('bio', 'Unknown'))
    template = template.replace('{{USER_GENDER}}', USER_VARIABLES.get('gender', 'Unknown'))
    template = template.replace('{{USER_BIRTH_DATE}}', USER_VARIABLES.get('birth_date', 'Unknown'))
    template = template.replace('{{USER_AGE}}', str(USER_VARIABLES.get('age', 'Unknown')))
    template = template.replace('{{USER_LOCATION}}', USER_VARIABLES.get('location', 'Unknown'))
    template = template.replace('{{USER_GROUPS}}', USER_VARIABLES.get('groups', ''))

    return template


def replace_prompt_variable(template: str, prompt: str) -> str:
    def replacement_function(match):
        full_match = match.group(0).lower()  # Normalize to lowercase for consistent handling
        start_length = match.group(1)
        end_length = match.group(2)
        middle_length = match.group(3)

        if full_match == '{{prompt}}':
            return prompt
        elif start_length is not None:
            return prompt[: int(start_length)]
        elif end_length is not None:
            return prompt[-int(end_length) :]
        elif middle_length is not None:
            middle_length = int(middle_length)
            if len(prompt) <= middle_length:
                return prompt
            start = prompt[: math.ceil(middle_length / 2)]
            end = prompt[-math.floor(middle_length / 2) :]
            return f'{start}...{end}'
        return ''

    # Updated regex pattern to make it case-insensitive with the `(?i)` flag
    pattern = r'(?i){{prompt}}|{{prompt:start:(\d+)}}|{{prompt:end:(\d+)}}|{{prompt:middletruncate:(\d+)}}'
    template = re.sub(pattern, replacement_function, template)
    return template


def truncate_content(content: str, max_chars: int, mode: str = 'middletruncate') -> str:
    """Truncate a string to max_chars using the specified mode.

    Modes:
        - middletruncate: keep beginning and end, join with '...'
        - start: keep first max_chars characters
        - end: keep last max_chars characters
    """
    if not content or len(content) <= max_chars:
        return content

    if mode == 'start':
        return content[:max_chars]
    elif mode == 'end':
        return content[-max_chars:]
    else:  # middletruncate
        half = max_chars // 2
        return f'{content[:half]}...{content[-(max_chars - half) :]}'


def apply_content_filter(messages: list[dict], filter_str: str) -> list[dict]:
    """Apply a content filter to each message's content.

    filter_str is like 'middletruncate:500', 'start:200', or 'end:200'.
    Returns a new list with truncated content (original messages are not mutated).
    """
    parts = filter_str.split(':')
    if len(parts) != 2:
        return messages

    mode = parts[0].lower()
    try:
        max_chars = int(parts[1])
    except ValueError:
        return messages

    if mode not in ('middletruncate', 'start', 'end'):
        return messages

    result = []
    for msg in messages:
        new_msg = dict(msg)
        if isinstance(new_msg.get('content'), str):
            new_msg['content'] = truncate_content(new_msg['content'], max_chars, mode)
        elif isinstance(new_msg.get('content'), list):
            new_content = []
            for item in new_msg['content']:
                if isinstance(item, dict) and item.get('type') == 'text':
                    new_item = dict(item)
                    new_item['text'] = truncate_content(item.get('text', ''), max_chars, mode)
                    new_content.append(new_item)
                else:
                    new_content.append(item)
            new_msg['content'] = new_content
        result.append(new_msg)
    return result


def replace_messages_variable(template: str, messages: Optional[list[dict]] = None) -> str:
    def replacement_function(match):
        # Groups: (1) filter for bare MESSAGES
        #         (2) START count, (3) filter for START
        #         (4) END count,   (5) filter for END
        #         (6) MIDDLE count,(7) filter for MIDDLE
        bare_filter = match.group(1)
        start_length = match.group(2)
        start_filter = match.group(3)
        end_length = match.group(4)
        end_filter = match.group(5)
        middle_length = match.group(6)
        middle_filter = match.group(7)

        # If messages is None, handle it as an empty list
        if messages is None:
            return ''

        # Select messages based on the variant
        if start_length is not None:
            selected = messages[: int(start_length)]
            content_filter = start_filter
        elif end_length is not None:
            selected = messages[-int(end_length) :]
            content_filter = end_filter
        elif middle_length is not None:
            mid = int(middle_length)
            if len(messages) <= mid:
                selected = messages
            else:
                half = mid // 2
                start_msgs = messages[:half]
                end_msgs = messages[-half:] if mid % 2 == 0 else messages[-(half + 1) :]
                selected = start_msgs + end_msgs
            content_filter = middle_filter
        else:
            # Bare {{MESSAGES}} or {{MESSAGES|filter}}
            selected = messages
            content_filter = bare_filter

        # Apply content filter if present
        if content_filter:
            selected = apply_content_filter(selected, content_filter)

        return get_messages_content(selected)

    template = re.sub(
        r'(?:'
        r'\{\{MESSAGES(?:\|(\w+:\d+))?\}\}'
        r'|\{\{MESSAGES:START:(\d+)(?:\|(\w+:\d+))?\}\}'
        r'|\{\{MESSAGES:END:(\d+)(?:\|(\w+:\d+))?\}\}'
        r'|\{\{MESSAGES:MIDDLETRUNCATE:(\d+)(?:\|(\w+:\d+))?\}\}'
        r')',
        replacement_function,
        template,
    )

    return template


# {{prompt:middletruncate:8000}}


# Let the context given here not distort the question,
# but illuminate it, so that the answer serves the one who asked.
async def rag_template(template: str, context: str, query: str):
    if template.strip() == '':
        template = DEFAULT_RAG_TEMPLATE

    template = await prompt_template(template)

    if '[context]' not in template and '{{CONTEXT}}' not in template:
        log.debug("WARNING: The RAG template does not contain the '[context]' or '{{CONTEXT}}' placeholder.")

    if '<context>' in context and '</context>' in context:
        log.debug(
            'WARNING: Potential prompt injection attack: the RAG '
            "context contains '<context>' and '</context>'. This might be "
            'nothing, or the user might be trying to hack something.'
        )

    query_placeholders = []
    if '[query]' in context:
        query_placeholder = '{{QUERY' + str(uuid.uuid4()) + '}}'
        template = template.replace('[query]', query_placeholder)
        query_placeholders.append((query_placeholder, '[query]'))

    if '{{QUERY}}' in context:
        query_placeholder = '{{QUERY' + str(uuid.uuid4()) + '}}'
        template = template.replace('{{QUERY}}', query_placeholder)
        query_placeholders.append((query_placeholder, '{{QUERY}}'))

    template = template.replace('[context]', context)
    template = template.replace('{{CONTEXT}}', context)

    template = template.replace('[query]', query)
    template = template.replace('{{QUERY}}', query)

    for query_placeholder, original_placeholder in query_placeholders:
        template = template.replace(query_placeholder, original_placeholder)

    return template


def filter_substantive_messages_for_title(messages: list[dict]) -> list[dict]:
    """Filter out pure greeting turns ('hellow', 'hi', etc.) when real topic messages exist."""
    if not messages:
        return []
    filtered: list[dict] = []
    skip_next_assistant = False
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get('role', '')
        content = m.get('content', '')
        if role == 'user' and isinstance(content, str) and is_greeting_or_placeholder_message(content):
            skip_next_assistant = True
            continue
        if role == 'assistant' and skip_next_assistant:
            skip_next_assistant = False
            continue
        skip_next_assistant = False
        filtered.append(m)
    return filtered if filtered else messages


async def title_generation_template(template: str, messages: list[dict], user: Optional[Any] = None) -> str:
    effective_messages = filter_substantive_messages_for_title(messages)
    prompt = get_last_user_message(effective_messages) or get_last_user_message(messages)
    template = replace_prompt_variable(template, prompt)
    template = replace_messages_variable(template, effective_messages)

    template = await prompt_template(template, user)

    return template


async def follow_up_generation_template(template: str, messages: list[dict], user: Optional[Any] = None) -> str:
    prompt = get_last_user_message(messages)
    template = replace_prompt_variable(template, prompt)
    template = replace_messages_variable(template, messages)

    template = await prompt_template(template, user)
    return template


async def tags_generation_template(template: str, messages: list[dict], user: Optional[Any] = None) -> str:
    prompt = get_last_user_message(messages)
    template = replace_prompt_variable(template, prompt)
    template = replace_messages_variable(template, messages)

    template = await prompt_template(template, user)
    return template


async def image_prompt_generation_template(template: str, messages: list[dict], user: Optional[Any] = None) -> str:
    prompt = get_last_user_message(messages)
    template = replace_prompt_variable(template, prompt)
    template = replace_messages_variable(template, messages)

    template = await prompt_template(template, user)
    return template


async def emoji_generation_template(template: str, prompt: str, user: Optional[Any] = None) -> str:
    template = replace_prompt_variable(template, prompt)
    template = await prompt_template(template, user)

    return template


async def autocomplete_generation_template(
    template: str,
    prompt: str,
    messages: Optional[list[dict]] = None,
    type: Optional[str] = None,
    user: Optional[Any] = None,
) -> str:
    template = template.replace('{{TYPE}}', type if type else '')
    template = replace_prompt_variable(template, prompt)
    template = replace_messages_variable(template, messages)

    template = await prompt_template(template, user)
    return template


async def query_generation_template(template: str, messages: list[dict], user: Optional[Any] = None) -> str:
    prompt = get_last_user_message(messages)
    template = replace_prompt_variable(template, prompt)
    template = replace_messages_variable(template, messages)

    template = await prompt_template(template, user)
    return template


def moa_response_generation_template(template: str, prompt: str, responses: list[str]) -> str:
    def replacement_function(match):
        full_match = match.group(0)
        start_length = match.group(1)
        end_length = match.group(2)
        middle_length = match.group(3)

        if full_match == '{{prompt}}':
            return prompt
        elif start_length is not None:
            return prompt[: int(start_length)]
        elif end_length is not None:
            return prompt[-int(end_length) :]
        elif middle_length is not None:
            middle_length = int(middle_length)
            if len(prompt) <= middle_length:
                return prompt
            start = prompt[: math.ceil(middle_length / 2)]
            end = prompt[-math.floor(middle_length / 2) :]
            return f'{start}...{end}'
        return ''

    template = re.sub(
        r'{{prompt}}|{{prompt:start:(\d+)}}|{{prompt:end:(\d+)}}|{{prompt:middletruncate:(\d+)}}',
        replacement_function,
        template,
    )

    responses = [f'"""{response}"""' for response in responses]
    responses = '\n\n'.join(responses)

    template = template.replace('{{responses}}', responses)
    return template


def tools_function_calling_generation_template(template: str, tools_specs: str) -> str:
    template = template.replace('{{TOOLS}}', tools_specs)
    return template
