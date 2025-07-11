import boto3

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENV: str = "local"

    API_KEY: str = "test"

    PORTAL_API_URL: str = "http://host.docker.internal:8000/api/v1/external"

    @field_validator("API_KEY")
    def validate_api_key(cls, v):
        # if the key is from SSM, it will be fetched here
        # check if it matches pattern /{ENV}/data_access/API_KEY
        if v.startswith("/"):
            ssm = boto3.client("ssm", region_name="ap-southeast-1")
            v = ssm.get_parameter(
                Name=f"/{cls.ENV}/data_access/API_KEY", WithDecryption=True
            )["Parameter"]["Value"]

        return v


settings = Settings()
