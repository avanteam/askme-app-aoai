# 🔐 Configuration Permissions API OVH pour AskMe DNS

## ⚠️ **Action Requise**

Les nouvelles clés API OVH ont été configurées mais nécessitent l'activation des permissions pour fonctionner.

## 🔑 **Informations de l'Application**

```
```

## 📋 **Permissions Requises**

### **🎯 Permissions Minimales pour DNS**

L'application **AskMeAvanteamSaaS** doit avoir les permissions suivantes :

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/domain/zone` | Lister les zones DNS |
| `GET` | `/domain/zone/avanteam-saas.com/record` | Lister les enregistrements |
| `GET` | `/domain/zone/avanteam-saas.com/record/*` | Détails d'un enregistrement |
| `POST` | `/domain/zone/avanteam-saas.com/record` | Créer un enregistrement |
| `POST` | `/domain/zone/avanteam-saas.com/refresh` | Appliquer les changements |
| `DELETE` | `/domain/zone/avanteam-saas.com/record/*` | Supprimer un enregistrement (optionnel) |

### **🔧 Configuration via OVH Manager**

1. **Se connecter** au [Manager OVHcloud](https://www.ovh.com/manager/)
2. **Aller dans** "API & Services" → "Tokens API"
3. **Trouver l'application** "AskMeAvanteamSaaS"
4. **Cliquer sur** "Gérer les autorisations"
5. **Ajouter les permissions** listées ci-dessus

### **🌐 Configuration via Lien Direct**

**Option A : Lien d'autorisation automatique**
```
https://eu.api.ovh.com/createToken/index.cgi?GET=/domain/zone&GET=/domain/zone/avanteam-saas.com/record&GET=/domain/zone/avanteam-saas.com/record/*&POST=/domain/zone/avanteam-saas.com/record&POST=/domain/zone/avanteam-saas.com/refresh&DELETE=/domain/zone/avanteam-saas.com/record/*
```

**Option B : Curl de génération de token**
```bash
curl -XPOST 'https://eu.api.ovh.com/1.0/auth/token' \
    -H 'X-Ovh-Application: 19ff5fa31fddfc15' \
    -H 'Content-type: application/json' \
    -d '{
        "accessRules": [
            {"method": "GET", "path": "/domain/zone"},
            {"method": "GET", "path": "/domain/zone/avanteam-saas.com/record"},
            {"method": "GET", "path": "/domain/zone/avanteam-saas.com/record/*"},
            {"method": "POST", "path": "/domain/zone/avanteam-saas.com/record"},
            {"method": "POST", "path": "/domain/zone/avanteam-saas.com/refresh"},
            {"method": "DELETE", "path": "/domain/zone/avanteam-saas.com/record/*"}
        ],
        "redirection": "https://github.com/avanteam/askme-rancher-catalog"
    }'
```

## ✅ **Validation des Permissions**

Une fois les permissions configurées, tester avec :

```bash
curl -H "X-Ovh-Application: 19ff5fa31fddfc15" \
     -H "X-Ovh-Consumer: ee08a1505e9ec0dcb6acac106d604f92" \
     -H "X-Ovh-Timestamp: $(date +%s)" \
     -H "X-Ovh-Signature: [signature]" \
     "https://eu.api.ovh.com/1.0/domain/zone"
```

## 🎯 **Résultat Attendu**

Après configuration des permissions :
- ✅ **Status 200** sur `/domain/zone`
- ✅ **Status 200** sur `/domain/zone/avanteam-saas.com/record`
- ✅ **Création d'enregistrements** fonctionnelle
- ✅ **DNS automatique** opérationnel dans Rancher

## 🚨 **Troubleshooting**

### **Erreur 403 Forbidden**
```json
{"class":"Client::Forbidden","message":"This call has not been granted"}
```
**Solution** : Configurer les permissions dans OVH Manager

### **Erreur 400 Bad Request**
```json
{"class":"Client::BadRequest","message":"Invalid signature"}
```
**Solution** : Vérifier les clés Application Key/Secret/Consumer Key

### **Erreur 404 Not Found**
```json
{"class":"Client::NotFound","message":"The requested object does not exist"}
```
**Solution** : Vérifier que la zone `avanteam-saas.com` existe

## 📞 **Support**

Si les permissions ne fonctionnent pas :
1. **Vérifier** que l'application existe dans OVH Manager
2. **Confirmer** les permissions sur la zone DNS spécifique
3. **Attendre** 5-10 minutes pour la propagation
4. **Tester** avec un simple GET sur `/domain/zone`

**🎯 Une fois les permissions configurées, l'intégration DNS AskMe sera 100% opérationnelle !**