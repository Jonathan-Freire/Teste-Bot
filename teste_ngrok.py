# teste_ngrok.py
import subprocess
import time
import requests
import json

print("🔍 Diagnóstico do Ngrok\n")

# 1. Verificar se ngrok está no PATH
print("1. Verificando ngrok no PATH...")
result = subprocess.run(["where", "ngrok"], capture_output=True, text=True, shell=True)
if result.returncode == 0:
    print(f"   ✅ Ngrok encontrado em: {result.stdout.strip()}")
else:
    print("   ❌ Ngrok não está no PATH")

# 2. Verificar versão
print("\n2. Verificando versão do ngrok...")
result = subprocess.run(["ngrok", "version"], capture_output=True, text=True, shell=True)
if result.returncode == 0:
    print(f"   ✅ {result.stdout.strip()}")
else:
    print("   ❌ Não foi possível obter a versão")

# 3. Verificar se já está rodando
print("\n3. Verificando se ngrok já está rodando...")
try:
    response = requests.get("http://localhost:4040/api/tunnels", timeout=2)
    if response.status_code == 200:
        data = response.json()
        if data.get("tunnels"):
            print("   ⚠️  Ngrok já está rodando com túneis ativos:")
            for tunnel in data["tunnels"]:
                print(f"      - {tunnel.get('public_url')}")
        else:
            print("   ✅ Ngrok está rodando mas sem túneis")
    else:
        print(f"   ❌ Status code: {response.status_code}")
except:
    print("   ℹ️  Ngrok não está rodando")

# 4. Testar criação de túnel
print("\n4. Testando criação de túnel...")
print("   Iniciando ngrok http 8000...")
processo = subprocess.Popen(["ngrok", "http", "8000"], 
                           creationflags=subprocess.CREATE_NEW_CONSOLE)
time.sleep(5)

try:
    response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
    data = response.json()
    if data.get("tunnels"):
        print("   ✅ Túnel criado com sucesso!")
        for tunnel in data["tunnels"]:
            print(f"      URL: {tunnel.get('public_url')}")
    else:
        print("   ❌ Nenhum túnel foi criado")
except Exception as e:
    print(f"   ❌ Erro: {e}")

input("\nPressione ENTER para encerrar o teste...")
processo.terminate()