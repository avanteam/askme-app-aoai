#!/bin/bash
# Script de test de connexion MongoDB
echo "🔍 Test de connexion MongoDB..."

# Déployer le pod de test
kubectl apply -f mongodb-test-pod.yaml

# Attendre que le pod soit prêt
kubectl wait --for=condition=Ready pod/mongodb-test -n askme-app --timeout=60s

# Test de connexion
echo "📡 Test de connexion au replica set..."
kubectl exec -n askme-app mongodb-test -- mongosh \
  "mongodb://mongodb-shared.askme-mongodb:27017/?replicaSet=rs0" \
  --username root \
  --password "AskMe-MongoDB-2024-Secure!" \
  --eval "
    print('✅ Connexion réussie !');
    print('📊 Status du replica set :');
    rs.status();
    print('📋 Databases existantes :');
    show dbs;
  "

# Nettoyage
echo "🧹 Nettoyage du pod de test..."
kubectl delete pod mongodb-test -n askme-app

echo "✅ Test terminé !"