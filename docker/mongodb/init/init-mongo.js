db = db.getSiblingDB('trading_db');

// Création des collections avec validation
db.createCollection('market_data', {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["symbol", "timestamp", "data"],
            properties: {
                symbol: {
                    bsonType: "string",
                    description: "Symbole de la paire de trading"
                },
                timestamp: {
                    bsonType: "date",
                    description: "Horodatage des données"
                },
                data: {
                    bsonType: "object",
                    description: "Données de marché"
                }
            }
        }
    }
});

db.createCollection('indicators', {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["symbol", "timestamp", "indicators"],
            properties: {
                symbol: {
                    bsonType: "string",
                    description: "Symbole de la paire de trading"
                },
                timestamp: {
                    bsonType: "date",
                    description: "Horodatage des indicateurs"
                },
                indicators: {
                    bsonType: "object",
                    description: "Valeurs des indicateurs techniques"
                }
            }
        }
    }
});

db.createCollection('trades', {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["symbol", "timestamp", "side", "price", "quantity"],
            properties: {
                symbol: {
                    bsonType: "string",
                    description: "Symbole de la paire de trading"
                },
                timestamp: {
                    bsonType: "date",
                    description: "Horodatage de la transaction"
                },
                side: {
                    enum: ["BUY", "SELL"],
                    description: "Type d'ordre"
                },
                price: {
                    bsonType: "double",
                    description: "Prix de la transaction"
                },
                quantity: {
                    bsonType: "double",
                    description: "Quantité échangée"
                },
                status: {
                    enum: ["PENDING", "COMPLETED", "FAILED"],
                    description: "Statut de la transaction"
                }
            }
        }
    }
});

// Création des index
db.market_data.createIndex({ "symbol": 1, "timestamp": -1 });
db.market_data.createIndex({ "timestamp": -1 });

db.indicators.createIndex({ "symbol": 1, "timestamp": -1 });
db.indicators.createIndex({ "timestamp": -1 });

db.trades.createIndex({ "symbol": 1, "timestamp": -1 });
db.trades.createIndex({ "timestamp": -1 });
db.trades.createIndex({ "status": 1 });
