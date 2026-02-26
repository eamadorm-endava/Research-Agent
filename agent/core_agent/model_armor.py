from google.cloud import modelarmor_v1
from google.cloud.modelarmor_v1.types import Template
from google.api_core.client_options import ClientOptions
from enum import StrEnum
import re


class SanitizationType(StrEnum):
    PROMPT = "user_prompt"
    RESPONSE = "agent_response"


class ModelArmor:
    # Code adapted from: https://docs.cloud.google.com/model-armor/manage-templates#create-ma-template
    def __init__(self, project_id: str, location: str):
        self.__project_id = project_id
        self.__location = location
        self.template_parent = f"projects/{self.project_id}/locations/{self.location}"

        # Configure the regional endpoint
        endpoint = f"modelarmor.{self.location}.rep.googleapis.com"
        client_options = ClientOptions(api_endpoint=endpoint)
        self.__client = modelarmor_v1.ModelArmorClient(
            transport="rest",
            client_options=client_options,
        )

    @property
    def project_id(self):
        return self.__project_id

    @property
    def location(self):
        return self.__location

    def list_templates(self) -> list[Template]:
        """
        List the available model armor templates

        Returns:
            list[Template] -> List of Model Armor templates previously created
        """

        request = modelarmor_v1.ListTemplatesRequest(
            parent=self.template_parent,
        )

        pager = self.__client.list_templates(request=request)

        return list(pager)

    def is_safe(
        self,
        sanitization_type: SanitizationType,
        template_id: str,
        text: str,
    ) -> bool:
        """
        Checks the model response to not include dangerous information, such as
        PII, unappropiate comments, and others

        Args:
            sanitization_type: SanitizationType -> Define whether to sanitize the user prompt
                                                    or the agent response
            template_id: str -> Id of the template to be used. Ex: "my-template-id"
            text: str -> The user prompt or agent response text

        Return:
            bool -> True if safe, otherwise False
        """

        # Code adapted from:
        # https://docs.cloud.google.com/model-armor/sanitize-prompts-responses#sanitize-prompts
        # https://docs.cloud.google.com/model-armor/sanitize-prompts-responses#sanitize-model

        template_pattern = r"^\w+[\w-]*$"

        if not isinstance(template_id, str) or not re.match(
            template_pattern,
            template_id,
        ):
            raise ValueError(
                "template_id can have letters, numbers, underscores and hyphens, must be 63 characters "
                "or less and cannot start with a hyphen or contain spaces."
            )

        # Initialize request
        data = modelarmor_v1.DataItem(text=text)

        template_name = f"{self.template_parent}/templates/{template_id}"

        if sanitization_type == SanitizationType.PROMPT:
            sanitization_request = modelarmor_v1.SanitizeUserPromptRequest(
                name=template_name, user_prompt_data=data
            )

            sanitization_response = self.__client.sanitize_user_prompt(
                request=sanitization_request
            )

        elif sanitization_type == SanitizationType.RESPONSE:
            sanitization_request = modelarmor_v1.SanitizeModelResponseRequest(
                name=template_name, model_response_data=data
            )

            sanitization_response = self.__client.sanitize_model_response(
                request=sanitization_request
            )

        else:
            raise ValueError(f"Sanitization Type not supported: {sanitization_type}")

        unsafe_match_result = (
            sanitization_response.sanitization_result.filter_match_state.name
        )

        return unsafe_match_result != "MATCH_FOUND"
