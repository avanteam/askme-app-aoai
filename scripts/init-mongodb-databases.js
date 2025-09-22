/**
 * Script d'initialisation MongoDB pour AskMe
 * Crée les databases et users pour chaque client
 *
 * Usage: mongosh "mongodb://root:password@mongodb-shared.askme-mongodb:27017/?replicaSet=rs0" --file init-mongodb-databases.js
 */

// Configuration des clients et leurs databases
const clients = [
    {
        clientId: "avanteam",
        database: "askme_avanteam",
        username: "askme_avanteam_user",
        description: "Base de données pour le client principal Avanteam"
    },
    {
        clientId: "qsaas",
        database: "askme_qsaas",
        username: "askme_qsaas_user",
        description: "Base de données pour le client QSaaS"
    }
    // Ajouter d'autres clients ici selon les besoins
];

print("🚀 Initialisation des bases de données MongoDB pour AskMe");
print("===========================================================");

// Se connecter à la database admin
use admin;

// Vérifier la connexion et les privilèges
try {
    const status = db.runCommand({connectionStatus: 1});
    print(`✅ Connecté en tant que: ${status.authInfo.authenticatedUsers[0].user}`);
} catch (e) {
    print("❌ Erreur de connexion à MongoDB:", e);
    quit(1);
}

// Fonction pour générer un mot de passe sécurisé
function generateSecurePassword(length = 24) {
    const charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*";
    let password = "";
    for (let i = 0; i < length; i++) {
        password += charset.charAt(Math.floor(Math.random() * charset.length));
    }
    return password;
}

// Fonction pour créer une database et son utilisateur
function createClientDatabase(clientConfig) {
    print(`\n🔧 Configuration du client: ${clientConfig.clientId}`);
    print(`   Database: ${clientConfig.database}`);
    print(`   Username: ${clientConfig.username}`);

    // Générer un mot de passe sécurisé
    const password = generateSecurePassword();

    try {
        // Basculer vers la database du client
        use(clientConfig.database);

        // Créer les collections avec schéma de validation
        db.createCollection("conversations", {
            validator: {
                $jsonSchema: {
                    bsonType: "object",
                    required: ["_id", "userId", "type", "createdAt", "updatedAt"],
                    properties: {
                        _id: {bsonType: "string"},
                        userId: {bsonType: "string"},
                        type: {bsonType: "string", enum: ["conversation"]},
                        title: {bsonType: "string"},
                        createdAt: {bsonType: "string"},
                        updatedAt: {bsonType: "string"}
                    }
                }
            }
        });

        db.createCollection("messages", {
            validator: {
                $jsonSchema: {
                    bsonType: "object",
                    required: ["_id", "userId", "conversationId", "type", "role", "content", "createdAt"],
                    properties: {
                        _id: {bsonType: "string"},
                        userId: {bsonType: "string"},
                        conversationId: {bsonType: "string"},
                        type: {bsonType: "string", enum: ["message"]},
                        role: {bsonType: "string", enum: ["user", "assistant", "system", "tool"]},
                        content: {},  // Flexible pour supporter texte, images, etc.
                        createdAt: {bsonType: "string"},
                        updatedAt: {bsonType: "string"},
                        timestamp: {bsonType: "date"}
                    }
                }
            }
        });

        // Créer les index pour optimiser les performances
        print("   📊 Création des index...");

        // Index sur conversations
        db.conversations.createIndex({userId: 1, type: 1});
        db.conversations.createIndex({userId: 1, updatedAt: -1});

        // Index sur messages
        db.messages.createIndex({userId: 1, conversationId: 1, type: 1});
        db.messages.createIndex({conversationId: 1, timestamp: 1});
        db.messages.createIndex({userId: 1, type: 1});

        print("   ✅ Collections et index créés");

        // Créer l'utilisateur avec les permissions appropriées
        db.createUser({
            user: clientConfig.username,
            pwd: password,
            roles: [
                {role: "readWrite", db: clientConfig.database}
            ],
            customData: {
                description: clientConfig.description,
                createdBy: "AskMe MongoDB Initialization Script",
                createdAt: new Date().toISOString()
            }
        });

        print(`   ✅ Utilisateur '${clientConfig.username}' créé avec succès`);
        print(`   🔑 Mot de passe généré: ${password}`);
        print(`   🔗 Connection string: mongodb://${clientConfig.username}:${password}@mongodb-shared.askme-mongodb:27017/${clientConfig.database}?replicaSet=rs0&readPreference=secondaryPreferred`);

        // Insérer un document de test
        const testResult = db.conversations.insertOne({
            _id: "test-conversation",
            userId: "test-user",
            type: "conversation",
            title: "Test Conversation - Please Delete",
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        });

        if (testResult.acknowledged) {
            print("   ✅ Test d'écriture réussi");
            // Nettoyer le document de test
            db.conversations.deleteOne({_id: "test-conversation"});
        }

        return {
            success: true,
            clientId: clientConfig.clientId,
            database: clientConfig.database,
            username: clientConfig.username,
            password: password
        };

    } catch (e) {
        print(`   ❌ Erreur lors de la création de la database ${clientConfig.database}:`, e);
        return {
            success: false,
            clientId: clientConfig.clientId,
            error: e.toString()
        };
    }
}

// Traiter tous les clients
let results = [];
let successCount = 0;

for (let client of clients) {
    const result = createClientDatabase(client);
    results.push(result);
    if (result.success) {
        successCount++;
    }
}

// Résumé final
print("\n📋 RÉSUMÉ DE L'INITIALISATION");
print("============================");
print(`✅ Clients configurés avec succès: ${successCount}/${clients.length}`);

if (successCount > 0) {
    print("\n🔗 CONNECTION STRINGS À UTILISER DANS .env:");
    print("============================================");

    for (let result of results) {
        if (result.success) {
            print(`# Client ${result.clientId}:`);
            print(`MONGODB_URI=mongodb://${result.username}:${result.password}@mongodb-external:27017/${result.database}?replicaSet=rs0&readPreference=secondaryPreferred`);
            print(`MONGODB_DATABASE=${result.database}`);
            print("");
        }
    }

    print("⚠️  IMPORTANT:");
    print("   - Sauvegardez ces mots de passe dans votre gestionnaire de secrets");
    print("   - Configurez HISTORY_PROVIDER=MONGODB dans vos .env");
    print("   - Redémarrez vos applications après configuration");
}

print("\n🎉 Initialisation MongoDB terminée !");

// Afficher le statut final du replica set
print("\n🔍 STATUS DU REPLICA SET:");
print("=========================");
try {
    use admin;
    const rsStatus = rs.status();
    print(`Replica Set: ${rsStatus.set}`);
    print(`Membres actifs: ${rsStatus.members.length}`);
    for (let member of rsStatus.members) {
        print(`  - ${member.name}: ${member.stateStr} (${member.health === 1 ? 'Healthy' : 'Unhealthy'})`);
    }
} catch (e) {
    print("❌ Impossible de récupérer le status du replica set:", e);
}