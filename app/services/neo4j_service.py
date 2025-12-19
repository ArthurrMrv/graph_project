from neo4j import GraphDatabase
from app.config import settings


class Neo4jService:
    def __init__(self):
        self.driver = GraphDatabase.driver(settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD))

    def close(self):
        self.driver.close()

    def run_query(self, query, parameters=None):
        with self.driver.session() as session:
            result = session.run(query, parameters)
            return list(result)

    def create_constraints(self):
        queries = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Tweet) REQUIRE t.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Stock) REQUIRE s.ticker IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:TradingDay) REQUIRE d.date IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (h:HashTag) REQUIRE h.tag IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (tp:Topic) REQUIRE tp.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:NewsEvent) REQUIRE n.event_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (f:Factor) REQUIRE f.name IS UNIQUE",
        ]
        with self.driver.session() as session:
            for q in queries:
                session.run(q)


neo4j_service = Neo4jService()
