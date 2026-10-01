import hashlib, os, sys, json, time
from xinference.client import RESTfulClient

ENDPOINT = os.getenv('XINFERENCE_ENDPOINT', 'http://127.0.0.1:9997')
USERNAME = os.getenv('XINFERENCE_USERNAME', 'admin')
PASSWORD = os.getenv('XINFERENCE_PASSWORD', 'Woli@1211')

print(f'🚀 [Wolinet AI] Connecting to Xinference at {ENDPOINT}...')
client = RESTfulClient(ENDPOINT)

print(f'🔑 Authenticating as {USERNAME}...')
try:
    client.login(USERNAME, PASSWORD)
    print('✅ Login successful!')
except Exception as e:
    print(f'ℹ️ Auth note (continuing): {e}')

try:
    token = client._get_token()
    if token:
        hashed_ep = hashlib.sha256(ENDPOINT.encode('utf-8')).hexdigest()
        auth_dir = '/root/.xinference/auth'
        os.makedirs(auth_dir, exist_ok=True)
        with open(os.path.join(auth_dir, hashed_ep), 'w') as f:
            f.write(token)
        print('✅ Saved CLI token.')
except Exception as e:
    pass

print('🧹 Cleaning up and terminating all existing/stale models to free RAM...')
try:
    running_models = client.list_models()
    print(f'Found {len(running_models)} active model(s): {list(running_models.keys())}')
    for uid in list(running_models.keys()):
        print(f'  -> Terminating: {uid}...')
        try:
            client.terminate_model(uid)
            print(f'  ✅ Terminated: {uid}')
        except Exception as te:
            print(f'  ⚠️ Error terminating {uid}: {te}')
    time.sleep(2)
except Exception as e:
    print(f'⚠️ Warning during model cleanup: {e}')

print('🚀 Launching DeepSeek Coder 1.3B (Wolinet Coder Engine)...')
print('   Engine: llama.cpp | Format: ggufv2 | Quantization: Q4_K_M | CPU (n_ctx=2048, n_parallel=1)')
model_uid = client.launch_model(
    model_name='deepseek-coder-instruct',
    model_uid='deepseek-coder-instruct',
    model_engine='llama.cpp',
    model_format='ggufv2',
    model_size_in_billions='1_3',
    quantization='Q4_K_M',
    n_gpu=None,
    n_gpu_layers=0,
    n_ctx=2048,
    n_parallel=1,
)

print('🎉 SUCCESS! Model is running!')
print(f'   Model UID: {model_uid}')
print(f'   Display Name: Wolinet Coder (wolinet-coder)')
print(f'   Status: Ready for requests from LiteLLM (lango) and Wolinex (Open WebUI)')
