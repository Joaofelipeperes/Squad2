import json
import requests

# Configurações da instância local
CKAN_URL = "http://localhost:5000"
API_KEY = "7446a8f0-5431-4e39-a1d5-aede1a387167" 

HEADERS = {
    "Authorization": API_KEY,
    "Content-Type": "application/json"
}

def create_or_get_organization(org_data):
    """Cria a organização caso não exista e retorna o ID."""
    org_name = org_data['name']
    check_url = f"{CKAN_URL}/api/3/action/organization_show?id={org_name}"
    
    res = requests.get(check_url, headers=HEADERS)
    if res.status_code == 200:
        return res.json()['result']['id']

    create_url = f"{CKAN_URL}/api/3/action/organization_create"
    payload = {
        "name": org_name,
        "title": org_data.get('title', org_name),
        "description": org_data.get('description', ''),
        "image_url": org_data.get('image_url', '')
    }
    
    res = requests.post(create_url, headers=HEADERS, json=payload)
    if res.status_code == 200:
        return res.json()['result']['id']
    else:
        print(f"Erro ao criar organização {org_name}: {res.text}")
        return None

def create_or_get_group(group_data):
    """Cria o grupo (categoria) caso não exista e retorna o dicionário formatado."""
    group_name = group_data['name']
    check_url = f"{CKAN_URL}/api/3/action/group_show?id={group_name}"
    
    res = requests.get(check_url, headers=HEADERS)
    if res.status_code == 200:
        return {"name": group_name}

    create_url = f"{CKAN_URL}/api/3/action/group_create"
    payload = {
        "name": group_name,
        "title": group_data.get('title', group_name),
        "description": group_data.get('description', '')
    }
    
    res = requests.post(create_url, headers=HEADERS, json=payload)
    if res.status_code == 200:
        return {"name": group_name}
    else:
        print(f"Erro ao criar grupo {group_name}: {res.text}")
        return None

def import_datasets(filepath):
    """Processa o JSON e faz a ingestão dos pacotes na instância local."""
    with open(filepath, 'r', encoding='utf-8') as f:
        datasets = json.load(f)

    for ds in datasets:
        print(f"Processando dataset: {ds['name']}...")
        
        # 1. Configurar Organização
        org_id = None
        if 'organization' in ds and ds['organization']:
            org_id = create_or_get_organization(ds['organization'])

        # 2. Configurar Grupos
        group_list = []
        for g in ds.get('groups', []):
            group_obj = create_or_get_group(g)
            if group_obj:
                group_list.append(group_obj)

        # 3. Limpar e configurar Tags
        tags = [{"name": t['name']} for t in ds.get('tags', [])]

        # 4. Configurar Recursos (apontando para a URL externa original)
        resources = []
        for res in ds.get('resources', []):
            resources.append({
                "name": res.get("name"),
                "description": res.get("description", ""),
                "format": res.get("format"),
                "url": res.get("url") # Mantém vínculo original
            })

        # 5. Montar payload do Dataset
        payload = {
            "name": ds["name"],
            "title": ds["title"],
            "notes": ds.get("notes", ""),
            "author": ds.get("author", ""),
            "author_email": ds.get("author_email", ""),
            "maintainer": ds.get("maintainer", ""),
            "maintainer_email": ds.get("maintainer_email", ""),
            "license_id": ds.get("license_id", ""),
            "owner_org": org_id,
            "groups": group_list,
            "tags": tags,
            "extras": ds.get("extras", []),
            "resources": resources
        }

        # 6. Criar Dataset
        create_url = f"{CKAN_URL}/api/3/action/package_create"
        resp = requests.post(create_url, headers=HEADERS, json=payload)
        
        if resp.status_code == 200:
            print(f" -> Sucesso! Dataset '{ds['name']}' importado.")
        elif resp.status_code == 409:
            print(f" -> Aviso: O dataset '{ds['name']}' já existe na base local.")
        else:
            print(f" -> Erro ao importar dataset '{ds['name']}': {resp.text}")

if __name__ == "__main__":
    import_datasets("metadados_ckan_goias.json")