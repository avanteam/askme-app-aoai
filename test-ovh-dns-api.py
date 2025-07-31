#!/usr/bin/env python3
"""
Script de test pour l'API OVH DNS
Valide les credentials et les permissions pour la zone avanteam-saas.com
"""

import requests
import hashlib
import time
import json
from datetime import datetime

class OVHDNSTest:
    def __init__(self):
        # Credentials OVH mises à jour
        self.app_key = "667723080ddee6c8"
        self.app_secret = "27b34f18a775f69c848bc4aabd80601d"
        self.consumer_key = "d11d6ae732fa19235cf8aec58414eebd"
        self.endpoint = "https://eu.api.ovh.com/1.0"
        self.zone = "avanteam-saas.com"
        
    def _generate_signature(self, method: str, url: str, body: str, timestamp: str) -> str:
        """Génère la signature OVH requise pour l'authentification"""
        raw_data = f"{self.app_secret}+{self.consumer_key}+{method}+{url}+{body}+{timestamp}"
        return "$1$" + hashlib.sha1(raw_data.encode()).hexdigest()
    
    def _make_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Effectue une requête API OVH avec authentification"""
        url = f"{self.endpoint}{endpoint}"
        timestamp = str(int(time.time()))
        body = json.dumps(data) if data else ""
        
        signature = self._generate_signature(method, url, body, timestamp)
        
        headers = {
            "X-Ovh-Application": self.app_key,
            "X-Ovh-Consumer": self.consumer_key,
            "X-Ovh-Timestamp": timestamp,
            "X-Ovh-Signature": signature,
            "Content-Type": "application/json"
        }
        
        print(f"\n🔗 {method} {url}")
        print(f"📋 Headers: {json.dumps({k: v if k != 'X-Ovh-Signature' else v[:20]+'...' for k, v in headers.items()}, indent=2)}")
        if data:
            print(f"📄 Body: {json.dumps(data, indent=2)}")
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, data=body, timeout=30)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                raise ValueError(f"Méthode HTTP non supportée: {method}")
            
            print(f"📊 Status: {response.status_code}")
            print(f"📝 Response: {response.text[:500]}{'...' if len(response.text) > 500 else ''}")
            
            return {
                "status_code": response.status_code,
                "success": response.status_code < 400,
                "data": response.json() if response.text and response.status_code < 400 else None,
                "error": response.text if response.status_code >= 400 else None
            }
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur réseau: {e}")
            return {"status_code": 0, "success": False, "error": str(e)}
        except json.JSONDecodeError as e:
            print(f"❌ Erreur JSON: {e}")
            return {"status_code": response.status_code, "success": False, "error": f"JSON decode error: {e}"}

    def test_credentials(self):
        """Test 1: Vérifier les credentials et l'accès aux zones DNS"""
        print("\n" + "="*60)
        print("🔑 TEST 1: Validation des credentials OVH")
        print("="*60)
        
        result = self._make_request("GET", "/domain/zone")
        if result["success"]:
            zones = result["data"] or []
            print(f"✅ Connexion réussie ! {len(zones)} zones trouvées")
            if self.zone in zones:
                print(f"✅ Zone '{self.zone}' accessible")
                return True
            else:
                print(f"❌ Zone '{self.zone}' non trouvée dans: {zones[:10]}...")
                return False
        else:
            print(f"❌ Échec de connexion: {result['error']}")
            return False

    def test_zone_access(self):
        """Test 2: Accès aux enregistrements de la zone"""
        print("\n" + "="*60)
        print(f"🌐 TEST 2: Accès aux enregistrements de {self.zone}")
        print("="*60)
        
        result = self._make_request("GET", f"/domain/zone/{self.zone}/record")
        if result["success"]:
            records = result["data"] or []
            print(f"✅ Zone accessible ! {len(records)} enregistrements trouvés")
            
            # Afficher les premiers enregistrements A
            a_records = []
            for record_id in records[:5]:  # Limiter aux 5 premiers
                record_result = self._make_request("GET", f"/domain/zone/{self.zone}/record/{record_id}")
                if record_result["success"] and record_result["data"].get("fieldType") == "A":
                    record_data = record_result["data"]
                    a_records.append(f"{record_data.get('subDomain', '@')}.{self.zone} -> {record_data.get('target')}")
            
            if a_records:
                print(f"📋 Exemples d'enregistrements A:")
                for record in a_records:
                    print(f"   - {record}")
            
            return True
        else:
            print(f"❌ Impossible d'accéder aux enregistrements: {result['error']}")
            return False

    def test_record_creation(self):
        """Test 3: Création d'un enregistrement de test"""
        print("\n" + "="*60)
        print("🆕 TEST 3: Création d'enregistrement DNS de test")
        print("="*60)
        
        test_subdomain = f"test-api-{int(time.time())}"
        test_ip = "203.0.113.1"  # IP de test RFC 5737
        
        record_data = {
            "fieldType": "A",
            "subDomain": test_subdomain,
            "target": test_ip,
            "ttl": 300
        }
        
        result = self._make_request("POST", f"/domain/zone/{self.zone}/record", record_data)
        if result["success"]:
            record_id = result["data"]["id"]
            print(f"✅ Enregistrement créé ! ID: {record_id}")
            
            # Appliquer les changements
            refresh_result = self._make_request("POST", f"/domain/zone/{self.zone}/refresh")
            if refresh_result["success"]:
                print("✅ Changements appliqués à la zone DNS")
                
                # Nettoyer l'enregistrement de test
                delete_result = self._make_request("DELETE", f"/domain/zone/{self.zone}/record/{record_id}")
                if delete_result["success"]:
                    print("✅ Enregistrement de test supprimé")
                    # Appliquer la suppression
                    self._make_request("POST", f"/domain/zone/{self.zone}/refresh")
                    print("✅ Suppression appliquée")
                else:
                    print(f"⚠️  Impossible de supprimer l'enregistrement de test: {delete_result['error']}")
                    print(f"⚠️  Supprimez manuellement l'enregistrement {test_subdomain}.{self.zone}")
                
                return True
            else:
                print(f"❌ Impossible d'appliquer les changements: {refresh_result['error']}")
                return False
        else:
            print(f"❌ Impossible de créer l'enregistrement: {result['error']}")
            return False

    def test_permissions_summary(self):
        """Résumé des permissions disponibles"""
        print("\n" + "="*60)
        print("📋 RÉSUMÉ DES PERMISSIONS")
        print("="*60)
        
        permissions = [
            ("GET /domain/zone", "Lister les zones"),
            (f"GET /domain/zone/{self.zone}/record", "Lister les enregistrements"),
            (f"POST /domain/zone/{self.zone}/record", "Créer des enregistrements"),
            (f"POST /domain/zone/{self.zone}/refresh", "Appliquer les changements"),
            (f"DELETE /domain/zone/{self.zone}/record/*", "Supprimer des enregistrements")
        ]
        
        for endpoint, description in permissions:
            print(f"   {endpoint:<40} | {description}")

    def run_all_tests(self):
        """Exécute tous les tests"""
        print("🚀 Début des tests API OVH DNS")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔧 Application: AskMeAvanteamSaaS")
        print(f"🌐 Zone: {self.zone}")
        print(f"🔑 App Key: {self.app_key}")
        print(f"🔑 Consumer Key: {self.consumer_key[:20]}...")
        
        results = []
        
        # Test 1: Credentials
        results.append(("Credentials", self.test_credentials()))
        
        # Test 2: Zone access (seulement si credentials OK)
        if results[0][1]:
            results.append(("Zone Access", self.test_zone_access()))
            
            # Test 3: Record creation (seulement si zone accessible)
            if results[1][1]:
                results.append(("Record Creation", self.test_record_creation()))
        
        # Résumé final
        print("\n" + "="*60)
        print("🎯 RÉSULTATS FINAUX")
        print("="*60)
        
        all_passed = True
        for test_name, passed in results:
            status = "✅ PASSÉ" if passed else "❌ ÉCHEC"
            print(f"{test_name:<20} | {status}")
            if not passed:
                all_passed = False
        
        if all_passed:
            print("\n🎉 TOUS LES TESTS SONT PASSÉS !")
            print("✅ L'intégration DNS automatique AskMe est opérationnelle")
        else:
            print("\n⚠️  CERTAINS TESTS ONT ÉCHOUÉ")
            print("📖 Consultez OVH_API_PERMISSIONS_SETUP.md pour configurer les permissions")
        
        self.test_permissions_summary()
        
        return all_passed

if __name__ == "__main__":
    tester = OVHDNSTest()
    success = tester.run_all_tests()
    exit(0 if success else 1)