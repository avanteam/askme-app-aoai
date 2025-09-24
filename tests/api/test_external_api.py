#!/usr/bin/env python3
"""
Script de test pour l'API REST externe.

Usage:
    python test_external_api.py
"""

import asyncio
import httpx
import json
from datetime import datetime


# Configuration de test
BASE_URL = "http://localhost:50505"
TEST_API_KEY = "sk-test-external-api-12345"
TEST_CLIENT_IP = "127.0.0.1"


async def test_health_endpoint():
    """Test du endpoint de santé (sans authentification)."""
    print("🏥 Test Health Check...")

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/v1/health")

        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health OK - Status: {data['status']}")
            print(f"   Search Provider: {data.get('search_provider_status', {})}")
        else:
            print(f"❌ Health Check Failed: {response.text}")

        print()


async def test_capabilities_endpoint():
    """Test du endpoint des capacités."""
    print("📋 Test Capabilities...")

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/v1/capabilities")

        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Capabilities OK")
            print(f"   Max Results: {data['max_results_limit']}")
            print(f"   Features: {data['supported_features']}")
            print(f"   Rate Limits: {data['rate_limits']}")
        else:
            print(f"❌ Capabilities Failed: {response.text}")

        print()


async def test_api_welcome():
    """Test du endpoint d'accueil de l'API."""
    print("🏠 Test API Welcome...")

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/v1/")

        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API Welcome OK")
            print(f"   Version: {data['version']}")
            print(f"   Swagger UI: {data['documentation']['swagger_ui']}")
            print(f"   OpenAPI Spec: {data['documentation']['openapi_spec']}")
        else:
            print(f"❌ API Welcome Failed: {response.text}")

        print()


async def test_documentation_endpoints():
    """Test des endpoints de documentation."""
    print("📚 Test Documentation Endpoints...")

    async with httpx.AsyncClient() as client:
        # Test OpenAPI JSON
        response = await client.get(f"{BASE_URL}/openapi.json")
        print(f"OpenAPI JSON: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ OpenAPI spec loaded - Title: {data.get('info', {}).get('title', 'N/A')}")

        # Test Swagger UI
        response = await client.get(f"{BASE_URL}/docs")
        print(f"Swagger UI: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ Swagger UI accessible")

        # Test ReDoc UI
        response = await client.get(f"{BASE_URL}/redoc")
        print(f"ReDoc UI: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ ReDoc UI accessible")

        print()


async def test_search_without_auth():
    """Test de recherche sans authentification (doit échouer)."""
    print("🔒 Test Search sans authentification...")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/search",
            json={
                "query": "test query",
                "max_results": 5
            }
        )

        print(f"Status: {response.status_code}")
        if response.status_code == 401:
            print("✅ Authentification correctement requise")
        else:
            print(f"❌ Authentification non requise (problème): {response.text}")

        print()


async def test_search_with_invalid_auth():
    """Test de recherche avec authentification invalide."""
    print("🔑 Test Search avec API key invalide...")

    headers = {"Authorization": "Bearer invalid-key-123"}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/search",
            headers=headers,
            json={
                "query": "test query",
                "max_results": 5
            }
        )

        print(f"Status: {response.status_code}")
        if response.status_code == 401:
            data = response.json()
            print("✅ API key invalide correctement rejetée")
            print(f"   Error: {data.get('error_message', 'N/A')}")
        else:
            print(f"❌ API key invalide acceptée (problème): {response.text}")

        print()


async def test_search_with_valid_auth():
    """Test de recherche avec authentification valide (nécessite configuration)."""
    print("✅ Test Search avec API key valide...")
    print("⚠️  Note: Nécessite EXTERNAL_API_KEYS configuré dans .env")

    headers = {"Authorization": f"Bearer {TEST_API_KEY}"}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/search",
            headers=headers,
            json={
                "query": "Comment configurer Azure AD?",
                "max_results": 5,
                "include_metadata": True,
                "use_semantic_search": True
            }
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("✅ Recherche réussie!")
            print(f"   Query: {data['query']}")
            print(f"   Results: {len(data['results'])}")
            print(f"   Response Time: {data['response_time_ms']:.2f}ms")
            print(f"   Provider: {data['search_provider']}")

            if data['results']:
                first_result = data['results'][0]
                print(f"   First Result Score: {first_result['score']}")
                print(f"   First Result Preview: {first_result['content'][:100]}...")

        elif response.status_code == 401:
            data = response.json()
            print("⚠️  Authentification échouée - Vérifiez EXTERNAL_API_KEYS dans .env")
            print(f"   Error: {data.get('error_message', 'N/A')}")

        elif response.status_code == 503:
            data = response.json()
            print("⚠️  Search provider indisponible")
            print(f"   Error: {data.get('error_message', 'N/A')}")

        else:
            print(f"❌ Erreur inattendue: {response.text}")

        print()


async def test_rate_limiting():
    """Test du rate limiting."""
    print("⚡ Test Rate Limiting...")
    print("Envoi de 5 requêtes rapides...")

    headers = {"Authorization": f"Bearer {TEST_API_KEY}"}

    async with httpx.AsyncClient() as client:
        for i in range(5):
            response = await client.post(
                f"{BASE_URL}/api/v1/search",
                headers=headers,
                json={
                    "query": f"test query {i}",
                    "max_results": 1
                }
            )

            print(f"   Requête {i+1}: {response.status_code}")

            # Vérifier les headers de rate limiting
            limit = response.headers.get('X-RateLimit-Limit')
            remaining = response.headers.get('X-RateLimit-Remaining')
            reset = response.headers.get('X-RateLimit-Reset')

            if limit:
                print(f"      Rate Limit: {remaining}/{limit}, Reset: {reset}")

            if response.status_code == 429:
                print("✅ Rate limiting fonctionnel!")
                break

            # Petite pause entre les requêtes
            await asyncio.sleep(0.1)

        print()


async def main():
    """Fonction principale de test."""
    print("=" * 60)
    print("🧪 TEST DE L'API REST EXTERNE ASKME")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"Test Time: {datetime.now().isoformat()}")
    print()

    # Tests sans authentification
    await test_api_welcome()
    await test_health_endpoint()
    await test_capabilities_endpoint()
    await test_documentation_endpoints()

    # Tests d'authentification
    await test_search_without_auth()
    await test_search_with_invalid_auth()

    # Tests avec authentification (si configurée)
    await test_search_with_valid_auth()

    # Test du rate limiting (si authentification configurée)
    # await test_rate_limiting()

    print("=" * 60)
    print("🏁 TESTS TERMINÉS")
    print()
    print("📝 Pour tester complètement l'API:")
    print("1. Ajoutez dans votre .env:")
    print("   EXTERNAL_API_ENABLED=true")
    print(f'   EXTERNAL_API_KEYS="test_client:{TEST_API_KEY}:*"')
    print("2. Relancez l'application")
    print("3. Relancez ce script de test")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Tests interrompus par l'utilisateur")
    except Exception as e:
        print(f"\n❌ Erreur lors des tests: {e}")
        import traceback
        traceback.print_exc()