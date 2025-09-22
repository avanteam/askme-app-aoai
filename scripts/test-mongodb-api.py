#!/usr/bin/env python3
"""
Script de test API complète pour MongoDB
Teste toutes les endpoints /history/* avec MongoDB comme provider
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, List

import httpx


class AskMeAPITester:
    """Testeur pour l'API AskMe avec MongoDB"""

    def __init__(self, base_url: str = "http://localhost:50505", timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=timeout)
        self.test_user_id = "test-user-mongodb"
        self.test_conversation_id = None
        self.test_message_id = None

        # Statistiques des tests
        self.tests_total = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.test_results = []

    def print_header(self):
        """Afficher l'en-tête du test"""
        print("🧪 TEST API ASKME - MONGODB PROVIDER")
        print("=" * 50)
        print(f"Base URL: {self.base_url}")
        print(f"Test User ID: {self.test_user_id}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print()

    def print_test(self, test_name: str, status: str, details: str = ""):
        """Afficher le résultat d'un test"""
        self.tests_total += 1

        if status == "PASS":
            self.tests_passed += 1
            print(f"✅ {test_name}")
        elif status == "FAIL":
            self.tests_failed += 1
            print(f"❌ {test_name}")
            if details:
                print(f"   {details}")
        elif status == "SKIP":
            print(f"⏭️ {test_name} - SKIPPED")
            if details:
                print(f"   {details}")

        self.test_results.append({
            'test': test_name,
            'status': status,
            'details': details,
            'timestamp': datetime.now().isoformat()
        })

    async def test_health_check(self) -> bool:
        """Test de santé MongoDB"""
        try:
            response = await self.client.get(f"{self.base_url}/history/ensure")

            if response.status_code == 200:
                data = response.json()
                if "successfully" in data.get('message', '').lower():
                    self.print_test("MongoDB Health Check", "PASS")
                    return True
                else:
                    self.print_test("MongoDB Health Check", "FAIL",
                                    f"Unexpected message: {data.get('message')}")
                    return False
            else:
                self.print_test("MongoDB Health Check", "FAIL",
                                f"HTTP {response.status_code}: {response.text}")
                return False

        except Exception as e:
            self.print_test("MongoDB Health Check", "FAIL", f"Exception: {str(e)}")
            return False

    async def test_create_conversation(self) -> bool:
        """Test de création de conversation"""
        try:
            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": "Hello, this is a test conversation for MongoDB"
                    }
                ]
            }

            headers = {
                "Content-Type": "application/json",
                "X-MS-CLIENT-PRINCIPAL-ID": self.test_user_id,
                "X-MS-CLIENT-PRINCIPAL-NAME": "MongoDB Tester"
            }

            response = await self.client.post(
                f"{self.base_url}/history/generate",
                json=payload,
                headers=headers
            )

            if response.status_code == 200:
                data = response.json()
                if 'conversation_id' in data:
                    self.test_conversation_id = data['conversation_id']
                    self.print_test("Create Conversation", "PASS",
                                    f"Created conversation: {self.test_conversation_id}")
                    return True
                else:
                    self.print_test("Create Conversation", "FAIL",
                                    "No conversation_id in response")
                    return False
            else:
                self.print_test("Create Conversation", "FAIL",
                                f"HTTP {response.status_code}: {response.text}")
                return False

        except Exception as e:
            self.print_test("Create Conversation", "FAIL", f"Exception: {str(e)}")
            return False

    async def test_list_conversations(self) -> bool:
        """Test de liste des conversations"""
        try:
            headers = {
                "X-MS-CLIENT-PRINCIPAL-ID": self.test_user_id,
                "X-MS-CLIENT-PRINCIPAL-NAME": "MongoDB Tester"
            }

            response = await self.client.get(
                f"{self.base_url}/history/list",
                headers=headers
            )

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    # Vérifier que notre conversation est dans la liste
                    found = any(conv.get('id') == self.test_conversation_id for conv in data)
                    if found:
                        self.print_test("List Conversations", "PASS",
                                        f"Found {len(data)} conversations")
                        return True
                    else:
                        self.print_test("List Conversations", "FAIL",
                                        "Created conversation not found in list")
                        return False
                else:
                    self.print_test("List Conversations", "FAIL",
                                    "Empty or invalid conversation list")
                    return False
            else:
                self.print_test("List Conversations", "FAIL",
                                f"HTTP {response.status_code}: {response.text}")
                return False

        except Exception as e:
            self.print_test("List Conversations", "FAIL", f"Exception: {str(e)}")
            return False

    async def test_read_conversation(self) -> bool:
        """Test de lecture d'une conversation"""
        if not self.test_conversation_id:
            self.print_test("Read Conversation", "SKIP", "No conversation to read")
            return False

        try:
            payload = {
                "conversation_id": self.test_conversation_id
            }

            headers = {
                "Content-Type": "application/json",
                "X-MS-CLIENT-PRINCIPAL-ID": self.test_user_id,
                "X-MS-CLIENT-PRINCIPAL-NAME": "MongoDB Tester"
            }

            response = await self.client.post(
                f"{self.base_url}/history/read",
                json=payload,
                headers=headers
            )

            if response.status_code == 200:
                data = response.json()
                if 'messages' in data and len(data['messages']) > 0:
                    # Sauvegarder un message_id pour les tests suivants
                    for msg in data['messages']:
                        if msg.get('role') == 'user':
                            self.test_message_id = msg.get('id')
                            break

                    self.print_test("Read Conversation", "PASS",
                                    f"Found {len(data['messages'])} messages")
                    return True
                else:
                    self.print_test("Read Conversation", "FAIL",
                                    "No messages in conversation")
                    return False
            else:
                self.print_test("Read Conversation", "FAIL",
                                f"HTTP {response.status_code}: {response.text}")
                return False

        except Exception as e:
            self.print_test("Read Conversation", "FAIL", f"Exception: {str(e)}")
            return False

    async def test_update_conversation(self) -> bool:
        """Test de mise à jour d'une conversation"""
        if not self.test_conversation_id:
            self.print_test("Update Conversation", "SKIP", "No conversation to update")
            return False

        try:
            payload = {
                "conversation_id": self.test_conversation_id,
                "messages": [
                    {
                        "role": "user",
                        "content": "This is an additional test message"
                    },
                    {
                        "role": "assistant",
                        "content": "I received your additional message. MongoDB is working correctly!"
                    }
                ]
            }

            headers = {
                "Content-Type": "application/json",
                "X-MS-CLIENT-PRINCIPAL-ID": self.test_user_id,
                "X-MS-CLIENT-PRINCIPAL-NAME": "MongoDB Tester"
            }

            response = await self.client.post(
                f"{self.base_url}/history/update",
                json=payload,
                headers=headers
            )

            if response.status_code == 200:
                self.print_test("Update Conversation", "PASS")
                return True
            else:
                self.print_test("Update Conversation", "FAIL",
                                f"HTTP {response.status_code}: {response.text}")
                return False

        except Exception as e:
            self.print_test("Update Conversation", "FAIL", f"Exception: {str(e)}")
            return False

    async def test_rename_conversation(self) -> bool:
        """Test de renommage d'une conversation"""
        if not self.test_conversation_id:
            self.print_test("Rename Conversation", "SKIP", "No conversation to rename")
            return False

        try:
            new_title = f"MongoDB Test Conversation - {datetime.now().strftime('%H:%M:%S')}"

            payload = {
                "conversation_id": self.test_conversation_id,
                "title": new_title
            }

            headers = {
                "Content-Type": "application/json",
                "X-MS-CLIENT-PRINCIPAL-ID": self.test_user_id,
                "X-MS-CLIENT-PRINCIPAL-NAME": "MongoDB Tester"
            }

            response = await self.client.post(
                f"{self.base_url}/history/rename",
                json=payload,
                headers=headers
            )

            if response.status_code == 200:
                self.print_test("Rename Conversation", "PASS", f"New title: {new_title}")
                return True
            else:
                self.print_test("Rename Conversation", "FAIL",
                                f"HTTP {response.status_code}: {response.text}")
                return False

        except Exception as e:
            self.print_test("Rename Conversation", "FAIL", f"Exception: {str(e)}")
            return False

    async def test_message_feedback(self) -> bool:
        """Test de feedback sur un message"""
        if not self.test_message_id:
            self.print_test("Message Feedback", "SKIP", "No message to give feedback")
            return False

        try:
            payload = {
                "message_id": self.test_message_id,
                "feedback": "positive"
            }

            headers = {
                "Content-Type": "application/json",
                "X-MS-CLIENT-PRINCIPAL-ID": self.test_user_id,
                "X-MS-CLIENT-PRINCIPAL-NAME": "MongoDB Tester"
            }

            response = await self.client.post(
                f"{self.base_url}/history/message_feedback",
                json=payload,
                headers=headers
            )

            if response.status_code == 200:
                self.print_test("Message Feedback", "PASS")
                return True
            else:
                self.print_test("Message Feedback", "FAIL",
                                f"HTTP {response.status_code}: {response.text}")
                return False

        except Exception as e:
            self.print_test("Message Feedback", "FAIL", f"Exception: {str(e)}")
            return False

    async def test_clear_conversation(self) -> bool:
        """Test de vidage d'une conversation"""
        if not self.test_conversation_id:
            self.print_test("Clear Conversation", "SKIP", "No conversation to clear")
            return False

        try:
            payload = {
                "conversation_id": self.test_conversation_id
            }

            headers = {
                "Content-Type": "application/json",
                "X-MS-CLIENT-PRINCIPAL-ID": self.test_user_id,
                "X-MS-CLIENT-PRINCIPAL-NAME": "MongoDB Tester"
            }

            response = await self.client.post(
                f"{self.base_url}/history/clear",
                json=payload,
                headers=headers
            )

            if response.status_code == 200:
                self.print_test("Clear Conversation", "PASS")
                return True
            else:
                self.print_test("Clear Conversation", "FAIL",
                                f"HTTP {response.status_code}: {response.text}")
                return False

        except Exception as e:
            self.print_test("Clear Conversation", "FAIL", f"Exception: {str(e)}")
            return False

    async def test_delete_conversation(self) -> bool:
        """Test de suppression d'une conversation"""
        if not self.test_conversation_id:
            self.print_test("Delete Conversation", "SKIP", "No conversation to delete")
            return False

        try:
            payload = {
                "conversation_id": self.test_conversation_id
            }

            headers = {
                "Content-Type": "application/json",
                "X-MS-CLIENT-PRINCIPAL-ID": self.test_user_id,
                "X-MS-CLIENT-PRINCIPAL-NAME": "MongoDB Tester"
            }

            response = await self.client.delete(
                f"{self.base_url}/history/delete",
                json=payload,
                headers=headers
            )

            if response.status_code == 200:
                self.print_test("Delete Conversation", "PASS")
                return True
            else:
                self.print_test("Delete Conversation", "FAIL",
                                f"HTTP {response.status_code}: {response.text}")
                return False

        except Exception as e:
            self.print_test("Delete Conversation", "FAIL", f"Exception: {str(e)}")
            return False

    async def test_delete_all_conversations(self) -> bool:
        """Test de suppression de toutes les conversations"""
        try:
            headers = {
                "X-MS-CLIENT-PRINCIPAL-ID": self.test_user_id,
                "X-MS-CLIENT-PRINCIPAL-NAME": "MongoDB Tester"
            }

            response = await self.client.delete(
                f"{self.base_url}/history/delete_all",
                headers=headers
            )

            if response.status_code == 200:
                self.print_test("Delete All Conversations", "PASS")
                return True
            else:
                self.print_test("Delete All Conversations", "FAIL",
                                f"HTTP {response.status_code}: {response.text}")
                return False

        except Exception as e:
            self.print_test("Delete All Conversations", "FAIL", f"Exception: {str(e)}")
            return False

    def print_summary(self):
        """Afficher le résumé des tests"""
        print()
        print("📊 RÉSUMÉ DES TESTS")
        print("=" * 30)
        print(f"Total: {self.tests_total}")
        print(f"✅ Réussis: {self.tests_passed}")
        print(f"❌ Échoués: {self.tests_failed}")
        print(f"📈 Taux de réussite: {(self.tests_passed/self.tests_total*100):.1f}%" if self.tests_total > 0 else "N/A")

        if self.tests_failed > 0:
            print()
            print("❌ Tests échoués:")
            for result in self.test_results:
                if result['status'] == 'FAIL':
                    print(f"  - {result['test']}: {result['details']}")

    async def run_all_tests(self) -> bool:
        """Exécuter tous les tests"""
        self.print_header()

        # Tests en séquence (certains dépendent des précédents)
        tests = [
            self.test_health_check,
            self.test_create_conversation,
            self.test_list_conversations,
            self.test_read_conversation,
            self.test_update_conversation,
            self.test_rename_conversation,
            self.test_message_feedback,
            self.test_clear_conversation,
            self.test_delete_conversation,
            self.test_delete_all_conversations
        ]

        for test in tests:
            await test()

        self.print_summary()

        return self.tests_failed == 0

    async def cleanup(self):
        """Nettoyer les ressources"""
        await self.client.aclose()


async def main():
    """Fonction principale"""
    import argparse

    parser = argparse.ArgumentParser(description="Test API AskMe avec MongoDB")
    parser.add_argument("--url", default="http://localhost:50505", help="URL de base de l'API")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout en secondes")
    parser.add_argument("--output", help="Fichier de sortie JSON pour les résultats")

    args = parser.parse_args()

    tester = AskMeAPITester(base_url=args.url, timeout=args.timeout)

    try:
        success = await tester.run_all_tests()

        # Sauvegarder les résultats si demandé
        if args.output:
            results = {
                'timestamp': datetime.now().isoformat(),
                'base_url': args.url,
                'total_tests': tester.tests_total,
                'passed_tests': tester.tests_passed,
                'failed_tests': tester.tests_failed,
                'success_rate': (tester.tests_passed/tester.tests_total*100) if tester.tests_total > 0 else 0,
                'test_results': tester.test_results
            }

            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            print(f"\n💾 Résultats sauvegardés dans: {args.output}")

        # Code de sortie
        sys.exit(0 if success else 1)

    finally:
        await tester.cleanup()


if __name__ == "__main__":
    asyncio.run(main())