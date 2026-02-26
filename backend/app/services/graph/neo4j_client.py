from neo4j import GraphDatabase

from app.config import settings


class Neo4jClient:
    def __init__(self) -> None:
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self) -> None:
        self._driver.close()

    def run(self, query: str, **params: object) -> list[dict]:
        with self._driver.session() as session:
            result = session.run(query, **params)
            return [record.data() for record in result]


neo4j_client = Neo4jClient()
