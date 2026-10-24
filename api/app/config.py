"""Configuration de l'application, lue depuis les variables d'environnement (.env)."""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = Field(default="development", alias="APP_ENV")
    secret_key: str = Field(alias="SECRET_KEY", min_length=32)
    database_url: str = Field(alias="DATABASE_URL")
    timezone: str = Field(default="Europe/Paris", alias="APP_TIMEZONE")

    # Session et sécurité
    session_cookie_name: str = "etabli_session"
    csrf_cookie_name: str = "csrf_token"
    csrf_header_name: str = "X-CSRF-Token"
    session_duration_minutes: int = Field(default=600, alias="SESSION_DURATION_MINUTES")
    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")
    max_login_attempts: int = 5
    lockout_minutes: int = 15

    # Comptes de démonstration (seed)
    demo_password_gerant: str = Field(default="", alias="DEMO_PASSWORD_GERANT")
    demo_password_mecanicien: str = Field(default="", alias="DEMO_PASSWORD_MECANICIEN")

    # Mentions légales du garage (valeurs fictives en démo)
    garage_raison_sociale: str = Field(default="Garage Établi SARL", alias="GARAGE_RAISON_SOCIALE")
    garage_adresse: str = Field(default="12 rue des Ateliers, 69007 Lyon", alias="GARAGE_ADRESSE")
    garage_siret: str = Field(default="000 000 000 00000", alias="GARAGE_SIRET")
    garage_tva_intra: str = Field(default="FR00000000000", alias="GARAGE_TVA_INTRA")
    garage_capital: str = Field(default="10 000 €", alias="GARAGE_CAPITAL")
    garage_rcs: str = Field(default="RCS Lyon 000 000 000", alias="GARAGE_RCS")
    garage_telephone: str = Field(default="04 00 00 00 00", alias="GARAGE_TELEPHONE")
    garage_email: str = Field(default="contact@garage-etabli.test", alias="GARAGE_EMAIL")
    # Délai de paiement d'une facture (échéance = jour d'émission à Paris + délai). Le Code de
    # commerce plafonne le délai convenu à 60 jours. L'ancien nom de variable reste accepté.
    garage_delai_paiement_jours: int = Field(
        default=30,
        ge=0,
        le=60,
        validation_alias=AliasChoices(
            "GARAGE_DELAI_PAIEMENT_JOURS", "FACTURE_DELAI_PAIEMENT_JOURS"
        ),
    )

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
