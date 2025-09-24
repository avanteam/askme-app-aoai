#!/usr/bin/env python3
"""
Test rapide pour diagnostiquer les problèmes Swagger.
"""

import asyncio
import httpx

BASE_URL = "http://localhost:50505"

async def test_endpoints():
    print("🔍 Test des endpoints de documentation...")

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Test API Welcome
        try:
            response = await client.get(f"{BASE_URL}/api/v1/")
            print(f"✅ API Welcome: {response.status_code}")
            if response.status_code != 200:
                print(f"   Error: {response.text[:100]}")
        except Exception as e:
            print(f"❌ API Welcome failed: {e}")

        # Test OpenAPI JSON
        try:
            response = await client.get(f"{BASE_URL}/openapi.json")
            print(f"📋 OpenAPI JSON: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Title: {data.get('info', {}).get('title', 'N/A')}")
            else:
                print(f"   Error: {response.text[:100]}")
        except Exception as e:
            print(f"❌ OpenAPI JSON failed: {e}")

        # Test Swagger UI
        try:
            response = await client.get(f"{BASE_URL}/docs")
            print(f"📚 Swagger UI: {response.status_code}")
            if response.status_code == 200:
                print("   ✅ Swagger UI accessible")
            else:
                print(f"   Error: {response.text[:200]}")
        except Exception as e:
            print(f"❌ Swagger UI failed: {e}")

        # Test ReDoc UI
        try:
            response = await client.get(f"{BASE_URL}/redoc")
            print(f"📖 ReDoc UI: {response.status_code}")
            if response.status_code == 200:
                print("   ✅ ReDoc UI accessible")
            else:
                print(f"   Error: {response.text[:200]}")
        except Exception as e:
            print(f"❌ ReDoc UI failed: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(test_endpoints())
        print("\n📝 Instructions:")
        print("1. Si OpenAPI JSON fonctionne mais pas Swagger UI:")
        print("   - Problème de template HTML")
        print("2. Si rien ne fonctionne:")
        print("   - Vérifiez que l'app est bien redémarrée")
        print("   - Vérifiez les logs d'erreur de l'application")
        print("3. URLs à tester manuellement:")
        print(f"   - {BASE_URL}/api/v1/")
        print(f"   - {BASE_URL}/openapi.json")
        print(f"   - {BASE_URL}/docs")
    except Exception as e:
        print(f"❌ Erreur générale: {e}")