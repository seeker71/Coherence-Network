from neo4j import GraphDatabase

# URI examples: "neo4j://localhost", "neo4j+s://xxx.databases.neo4j.io"
URI = "neo4j+s://716f28e4.databases.neo4j.io"
AUTH = ("neo4j", "HyRHlocHxeIKVqfNJlLzxvMXu-YyUuQP8K6PES7aEEU")

with GraphDatabase.driver(URI, auth=AUTH) as driver:
    driver.verify_connectivity()
