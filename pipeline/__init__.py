"""jobtech — pipeline ETL médaillon (bronze → silver → gold → Data Warehouse).

Remplace les anciens scripts à plat (1_scrape / 2_clean / 3_load_dwh) par un
package cohérent, avec un contrat de données explicite entre couches et un
chargement transactionnel idempotent du schéma en étoile PostgreSQL.
"""

__all__ = ["config", "transforms", "lake"]
