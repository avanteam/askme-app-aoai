# Reference des Filtres - API Externe AskMe

## Vue d'ensemble

L'API externe AskMe supporte le filtrage OData sur plusieurs champs de l'index Azure Search. Cette reference liste tous les champs filtrables disponibles avec des exemples d'utilisation.

## Champs Filtrables Disponibles

### 1. `securityRights` (Collection de Strings)

**Description:** Droits d'acces requis pour consulter le document.

**Type:** `Collection(Edm.String)`

**Logique:** OR (au moins un droit doit correspondre)

**Exemples:**
```json
{
  "filters": {
    "securityRights": ["QDMAdmin"]
  }
}
```

```json
{
  "filters": {
    "securityRights": ["QDMAdmin", "QDMLecteur", "QDMContributeur"]
  }
}
```

**Cas d'usage typique:** Filtrer les documents selon les permissions de l'utilisateur connecte.

---

### 2. `metadata_storage_name` (String)

**Description:** Nom exact du fichier tel que stocke dans Azure Blob Storage.

**Type:** `Edm.String`

**Logique:** Egalite exacte (case-sensitive)

**Exemples:**
```json
{
  "filters": {
    "metadata_storage_name": "guide-installation.pdf"
  }
}
```

```json
{
  "filters": {
    "metadata_storage_name": "Manuel Utilisateur.docx"
  }
}
```

**Cas d'usage typique:** Rechercher uniquement dans un fichier specifique.

**Note:** Le nom doit correspondre exactement (espaces, majuscules, extension inclus).

---

### 3. `metadata_storage_path` (String)

**Description:** URL complete du fichier dans Azure Blob Storage.

**Type:** `Edm.String`

**Logique:** Egalite exacte

**Exemple:**
```json
{
  "filters": {
    "metadata_storage_path": "https://askmestorageprod.blob.core.windows.net/askme-navalgroup-poclighton-dev/bbafb8c8-6613-40ed-9a77-8927b34c6681/guide.pdf"
  }
}
```

**Cas d'usage typique:** Filtrer par URL complete lorsque vous avez l'identifiant unique du document.

---

### 4. `title` (String)

**Description:** Titre du document (version generique).

**Type:** `Edm.String`

**Logique:** Egalite exacte

**Exemple:**
```json
{
  "filters": {
    "title": "Installation Guide"
  }
}
```

**Cas d'usage typique:** Filtrer par titre de document (version anglaise/generique).

---

### 5. `titreDocument` (String)

**Description:** Titre du document (version francaise).

**Type:** `Edm.String`

**Logique:** Egalite exacte

**Exemples:**
```json
{
  "filters": {
    "titreDocument": "Manuel Utilisateur"
  }
}
```

```json
{
  "filters": {
    "titreDocument": "Guide d'Installation Office 365"
  }
}
```

**Cas d'usage typique:** Filtrer par titre de document (version francaise).

**Note:** Utilisez ce champ de preference pour les documents francais.

---

### 6. `parent_id` (String)

**Description:** Identifiant du document parent (pour les documents decoupes en chunks).

**Type:** `Edm.String`

**Logique:** Egalite exacte

**Exemple:**
```json
{
  "filters": {
    "parent_id": "doc-123456"
  }
}
```

**Cas d'usage typique:** Recuperer tous les chunks d'un document specifique.

---

## Combinaison de Filtres

### Logique AND (ET)

Plusieurs cles de filtres sont combinees avec AND logique.

**Exemple:**
```json
{
  "query": "configuration",
  "filters": {
    "metadata_storage_name": "guide.pdf",
    "securityRights": ["QDMAdmin"]
  }
}
```

**Resultat:** Documents qui correspondent a TOUS les criteres :
- Nom de fichier = "guide.pdf" **ET**
- Droits d'acces contiennent "QDMAdmin"

---

### Logique OR (OU)

Plusieurs valeurs dans une liste sont combinees avec OR logique.

**Exemple:**
```json
{
  "query": "procedure",
  "filters": {
    "securityRights": ["QDMAdmin", "QDMLecteur", "QDMContributeur"]
  }
}
```

**Resultat:** Documents qui ont **AU MOINS UN** des droits suivants :
- QDMAdmin **OU**
- QDMLecteur **OU**
- QDMContributeur

---

## Exemples Complets

### Exemple 1: Recherche par Nom de Fichier

**Besoin:** Trouver toutes les references a "Azure AD" dans le fichier "guide-azure.pdf"

```bash
curl -X POST "https://askme.your-domain.com/api/v1/search" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Azure AD",
    "max_results": 10,
    "filters": {
      "metadata_storage_name": "guide-azure.pdf"
    }
  }'
```

---

### Exemple 2: Recherche avec Permissions

**Besoin:** Rechercher "derogation" uniquement dans les documents accessibles par QDMAdmin ou QDMLecteur

```bash
curl -X POST "https://askme.your-domain.com/api/v1/search" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "derogation",
    "max_results": 20,
    "filters": {
      "securityRights": ["QDMAdmin", "QDMLecteur"]
    }
  }'
```

---

### Exemple 3: Recherche dans un Document Specifique par Titre

**Besoin:** Chercher "installation" uniquement dans le "Manuel Utilisateur"

```bash
curl -X POST "https://askme.your-domain.com/api/v1/search" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "installation",
    "max_results": 10,
    "filters": {
      "titreDocument": "Manuel Utilisateur"
    }
  }'
```

---

### Exemple 4: Filtres Combinees Complexes

**Besoin:** Rechercher "configuration" dans "guide.pdf" accessible par QDMAdmin

```bash
curl -X POST "https://askme.your-domain.com/api/v1/search" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "configuration",
    "max_results": 10,
    "filters": {
      "metadata_storage_name": "guide.pdf",
      "securityRights": ["QDMAdmin"],
      "titreDocument": "Guide de Configuration"
    }
  }'
```

**Note:** Tous les criteres doivent etre satisfaits (AND logique).

---

## Limitations et Notes Importantes

### Champs NON Filtrables

Les champs suivants existent dans l'index mais ne sont **PAS filtrables** :

- `chunk` (contenu du texte) - Utilisez le parametre `query` a la place
- `chunk_id` - Identifiant interne des chunks
- `fieldMetadata` - Metadonnees personnalisees
- `metadata_creation_date` - Date de creation
- `metadata_storage_last_modified` - Date de derniere modification
- `text_vector` - Vecteur d'embedding

### Sensibilite a la Casse

Les filtres sur les champs String sont **sensibles a la casse**. Assurez-vous que :
- Les noms de fichiers correspondent exactement
- Les titres sont correctement capitalises
- Les valeurs de `parent_id` sont exactes

### Performance

**Recommandations:**
1. Utilisez des filtres pour reduire l'ensemble de resultats avant la recherche semantique
2. Les filtres par `securityRights` sont optimises pour les controles d'acces
3. Evitez de combiner trop de filtres (max 3-4 recommande)

### Syntaxe OData

En interne, l'API convertit vos filtres en syntaxe OData Azure Search :

**Votre filtre:**
```json
{
  "metadata_storage_name": "guide.pdf"
}
```

**OData genere:**
```
metadata_storage_name eq 'guide.pdf'
```

**Votre filtre:**
```json
{
  "securityRights": ["QDMAdmin", "QDMLecteur"]
}
```

**OData genere:**
```
securityRights/any(r: r eq 'QDMAdmin' or r eq 'QDMLecteur')
```

---

## Verification des Champs Filtrables

Pour verifier les champs filtrables dans votre index Azure Search :

```bash
# Utiliser le script fourni
cd /path/to/askme-app-aoai
python ../list_filterable_fields.py
```

Le script affichera tous les champs de l'index avec leurs proprietes (filterable, searchable, sortable).

---

## Support

Pour toute question sur les filtres :

1. Consultez la documentation Swagger : `https://your-domain.com/docs`
2. Testez avec l'interface Swagger UI
3. Verifiez les logs de l'API pour les erreurs de filtrage

**Derniere mise a jour:** 2025-10-14
**Version API:** v1.0.0
