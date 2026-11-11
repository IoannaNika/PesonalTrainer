from garminconnect import Garmin
import argparse
import getpass

def connect_to_garmin(email, password):
    garmin = Garmin(email, password)
    try:
        garmin.login()
        print("Connected to Garmin Connect successfully!")
        return garmin
    except Exception as e:  
        print(f"Failed to connect to Garmin Connect: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Connect to Garmin Connect")
    parser.add_argument("--email", required=True, help="Garmin Connect email")
    parser.add_argument('--prompt-password', action='store_true', help="Prompt securely for the password")
    args = parser.parse_args()

    password = None
    if args.prompt_password:
        password = getpass.getpass("Enter password: ")
    else:
        raise ValueError("No password provided.")

    garmin = connect_to_garmin(args.email, password)

if __name__ == "__main__":
    main()






