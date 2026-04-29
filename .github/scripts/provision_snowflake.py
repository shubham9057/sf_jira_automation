import snowflake.connector
import os
import sys

def main():
    # Retrieve environment variables injected by GitHub Actions
    user_email = os.getenv('USER_EMAIL')
    role_name = os.getenv('ROLE_NAME')
    sf_account = os.getenv('SNOWFLAKE_ACCOUNT')
    sf_user = os.getenv('SNOWFLAKE_USER')
    private_key_data = os.getenv('SNOWFLAKE_PRIVATE_KEY')

    # Basic Validation
    if not all([user_email, role_name, sf_account, sf_user, private_key_data]):
        print("Error: Missing one or more required environment variables.")
        sys.exit(1)

    try:
        # Establish Connection using Key-Pair Auth
        ctx = snowflake.connector.connect(
            user=sf_user,
            account=sf_account,
            private_key=private_key_data.encode()
        )
        cs = ctx.cursor()

        print(f"Executing provisioning for: {user_email}")

        # Derive display/login name: first letter of firstname + lastname (uppercase)
        first_name = user_email.split('@')[0].split('.')[0].upper()
        last_name = user_email.split('@')[0].split('.')[1].upper()
        display_name = first_name[0] + last_name
        read_role = display_name + '_READ'
        readwrite_role = display_name + '_READWRITE'

        # -- Step 1: Use USERADMIN role to create the user
        cs.execute("USE ROLE USERADMIN;")

        cs.execute(f"""
        CREATE USER IF NOT EXISTS IDENTIFIER('{display_name}')
            LOGIN_NAME = '{display_name}'
            DISPLAY_NAME = '{display_name}'
            EMAIL = '{user_email}'
            MUST_CHANGE_PASSWORD = TRUE
            DEFAULT_ROLE = IDENTIFIER('{read_role}');
        """)

        # -- Step 2: Create custom roles (READ and READWRITE)
        cs.execute(f"CREATE ROLE IF NOT EXISTS IDENTIFIER('{read_role}');")
        cs.execute(f"CREATE ROLE IF NOT EXISTS IDENTIFIER('{readwrite_role}');")

        # -- Step 3: Grant roles to the user
        cs.execute(f"GRANT ROLE IDENTIFIER('{read_role}') TO USER IDENTIFIER('{display_name}');")
        cs.execute(f"GRANT ROLE IDENTIFIER('{readwrite_role}') TO USER IDENTIFIER('{display_name}');")

        # -- Step 4: Build role hierarchy (READWRITE inherits READ)
        cs.execute(f"GRANT ROLE IDENTIFIER('{read_role}') TO ROLE IDENTIFIER('{readwrite_role}');")

        # -- Grant custom roles to SYSADMIN for governance
        cs.execute(f"GRANT ROLE IDENTIFIER('{read_role}') TO ROLE SYSADMIN;")
        cs.execute(f"GRANT ROLE IDENTIFIER('{readwrite_role}') TO ROLE SYSADMIN;")

        # -- Step 5: Create database with same name as display name
        cs.execute("USE ROLE SYSADMIN;")

        cs.execute(f"CREATE DATABASE IF NOT EXISTS IDENTIFIER('{display_name}');")

        # -- Step 6: Grant privileges on the database to the custom roles
        cs.execute(f"GRANT USAGE ON DATABASE IDENTIFIER('{display_name}') TO ROLE IDENTIFIER('{read_role}');")
        cs.execute(f"GRANT USAGE ON ALL SCHEMAS IN DATABASE IDENTIFIER('{display_name}') TO ROLE IDENTIFIER('{read_role}');")
        cs.execute(f"GRANT SELECT ON ALL TABLES IN DATABASE IDENTIFIER('{display_name}') TO ROLE IDENTIFIER('{read_role}');")
        cs.execute(f"GRANT SELECT ON ALL VIEWS IN DATABASE IDENTIFIER('{display_name}') TO ROLE IDENTIFIER('{read_role}');")
        cs.execute(f"GRANT SELECT ON FUTURE TABLES IN DATABASE IDENTIFIER('{display_name}') TO ROLE IDENTIFIER('{read_role}');")
        cs.execute(f"GRANT SELECT ON FUTURE VIEWS IN DATABASE IDENTIFIER('{display_name}') TO ROLE IDENTIFIER('{read_role}');")
        cs.execute(f"GRANT USAGE ON FUTURE SCHEMAS IN DATABASE IDENTIFIER('{display_name}') TO ROLE IDENTIFIER('{read_role}');")

        cs.execute(f"GRANT USAGE ON DATABASE IDENTIFIER('{display_name}') TO ROLE IDENTIFIER('{readwrite_role}');")
        cs.execute(f"GRANT USAGE ON ALL SCHEMAS IN DATABASE IDENTIFIER('{display_name}') TO ROLE IDENTIFIER('{readwrite_role}');")
        cs.execute(f"GRANT CREATE SCHEMA ON DATABASE IDENTIFIER('{display_name}') TO ROLE IDENTIFIER('{readwrite_role}');")
        cs.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN DATABASE IDENTIFIER('{display_name}') TO ROLE IDENTIFIER('{readwrite_role}');")
        cs.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON FUTURE TABLES IN DATABASE IDENTIFIER('{display_name}') TO ROLE IDENTIFIER('{readwrite_role}');")
        cs.execute(f"GRANT CREATE TABLE ON ALL SCHEMAS IN DATABASE IDENTIFIER('{display_name}') TO ROLE IDENTIFIER('{readwrite_role}');")
        cs.execute(f"GRANT CREATE VIEW ON ALL SCHEMAS IN DATABASE IDENTIFIER('{display_name}') TO ROLE IDENTIFIER('{readwrite_role}');")
        cs.execute(f"GRANT USAGE ON FUTURE SCHEMAS IN DATABASE IDENTIFIER('{display_name}') TO ROLE IDENTIFIER('{readwrite_role}');")

        # -- Step 7: Grant warehouse usage
        cs.execute(f"GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE IDENTIFIER('{read_role}');")
        cs.execute(f"GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE IDENTIFIER('{readwrite_role}');")
        cs.close()
        ctx.close()
        print("Final Status: Success.")

    except Exception as e:
        print(f"Snowflake Operational Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()