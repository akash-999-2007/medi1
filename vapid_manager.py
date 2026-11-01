import os
import json
import base64
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

KEYS_FILE = Path(__file__).resolve().parent / "vapid_keys.json"

def base64url_encode(data: bytes) -> str:
    """Encode bytes to base64url string without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def generate_vapid_keys():
    """Generate ECDSA P-256 key pair in base64url format suitable for Web Push."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    
    # Raw 32-byte private key integer
    priv_num = private_key.private_numbers().private_value
    priv_bytes = priv_num.to_bytes(32, byteorder='big')
    private_b64 = base64url_encode(priv_bytes)
    
    # Raw 65-byte uncompressed public key point (0x04 + X + Y)
    pub_key = private_key.public_key()
    pub_bytes = pub_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    )
    public_b64 = base64url_encode(pub_bytes)
    
    return {
        "private_key": private_b64,
        "public_key": public_b64
    }

def get_or_create_vapid_keys():
    """Retrieve VAPID keys from env or file, or generate new ones automatically."""
    env_pub = os.environ.get("VAPID_PUBLIC_KEY")
    env_priv = os.environ.get("VAPID_PRIVATE_KEY")
    
    if env_pub and env_priv:
        return {
            "public_key": env_pub.strip(),
            "private_key": env_priv.strip()
        }
        
    if KEYS_FILE.exists():
        try:
            with open(KEYS_FILE, "r") as f:
                data = json.load(f)
                if data.get("public_key") and data.get("private_key"):
                    return data
        except Exception:
            pass
            
    # Generate new pair and save to json file
    keys = generate_vapid_keys()
    try:
        with open(KEYS_FILE, "w") as f:
            json.dump(keys, f, indent=2)
        print(f"[VAPID] Generated new Web Push VAPID keypair in {KEYS_FILE.name}")
    except Exception as e:
        print(f"[VAPID] Error saving keys to file: {e}")
        
    return keys

if __name__ == "__main__":
    keys = generate_vapid_keys()
    print("Generated Web Push VAPID Keys:")
    print("Public Key:")
    print(keys["public_key"])
    print("\nPrivate Key:")
    print(keys["private_key"])
