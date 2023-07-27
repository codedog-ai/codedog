from github import Github

from codedog.utils import get_access_token_by_installation_id, get_jwt_token

YOUR_APP_ID = 363842
installation_id = 39837873

private_key = """
-----BEGIN RSA PRIVATE KEY-----
-----END RSA PRIVATE KEY-----
"""

jwt_token = get_jwt_token(private_key, YOUR_APP_ID)

access_token = get_access_token_by_installation_id(installation_id, jwt_token)

github_client = Github(access_token)
print(github_client)
