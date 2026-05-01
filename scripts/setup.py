#!/usr/bin/env python3
"""
PlantMind AI - Automated Setup Script
Handles environment setup, database initialization, and dependency installation.
"""

import os
import sys
import subprocess
import argparse
import json
from pathlib import Path


def print_banner():
    """Print setup banner."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║              🏭 PlantMind AI - Setup Assistant               ║
║                                                              ║
║      Automated setup for the Smart Factory AI Platform       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")


def check_python_version():
    """Check if Python version is compatible."""
    print("📋 Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print(f"❌ Python {version.major}.{version.minor} is not supported.")
        print("   Please use Python 3.10 or higher.")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} detected")
    return True


def install_dependencies(venv_path=None):
    """Install Python dependencies."""
    print("\n📦 Installing dependencies...")
    
    pip_cmd = "pip"
    if venv_path:
        if os.name == 'nt':  # Windows
            pip_cmd = os.path.join(venv_path, "Scripts", "pip.exe")
        else:
            pip_cmd = os.path.join(venv_path, "bin", "pip")
    
    requirements = Path("requirements.txt")
    if not requirements.exists():
        print("❌ requirements.txt not found!")
        return False
    
    try:
        subprocess.run([pip_cmd, "install", "-r", "requirements.txt"], check=True)
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False


def create_virtual_environment():
    """Create Python virtual environment."""
    print("\n🐍 Creating virtual environment...")
    venv_path = Path("venv")
    
    if venv_path.exists():
        print("   Virtual environment already exists")
        return str(venv_path)
    
    try:
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print("✅ Virtual environment created")
        return str(venv_path)
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create virtual environment: {e}")
        return None


def setup_environment_file():
    """Create .env file from template."""
    print("\n⚙️  Setting up environment configuration...")
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        print("   .env file already exists")
        response = input("   Overwrite? (y/N): ").lower()
        if response != 'y':
            print("   Skipping .env setup")
            return True
    
    if not env_example.exists():
        print("❌ .env.example not found!")
        return False
    
    # Copy example file
    with open(env_example, 'r') as f:
        template = f.read()
    
    # Get user input for critical values
    print("\n   Please configure the following settings:")
    
    db_url = input("   Database URL [postgresql://plantmind:plantmind@localhost:5432/plantmind]: ").strip()
    if not db_url:
        db_url = "postgresql://plantmind:plantmind@localhost:5432/plantmind"
    
    secret_key = input("   App Secret Key [auto-generated]: ").strip()
    if not secret_key:
        import secrets
        secret_key = secrets.token_urlsafe(32)
        print(f"   Generated secret key: {secret_key[:16]}...")
    
    gmail_email = input("   Gmail SMTP Email [optional]: ").strip()
    gmail_password = input("   Gmail App Password [optional]: ").strip()
    
    # Replace values in template
    env_content = template
    env_content = env_content.replace(
        "postgresql://plantmind:plantmind@localhost:5432/plantmind",
        db_url
    )
    env_content = env_content.replace(
        "your-secret-key-here-change-in-production",
        secret_key
    )
    
    if gmail_email:
        env_content = env_content.replace("factory@gmail.com", gmail_email)
    if gmail_password:
        env_content = env_content.replace("your-gmail-app-password", gmail_password)
    
    with open(env_file, 'w') as f:
        f.write(env_content)
    
    print("✅ .env file created")
    return True


def create_directories():
    """Create necessary directories."""
    print("\n📁 Creating directories...")
    
    dirs = ["config", "logs", "data", "tests/sample_files"]
    for dir_name in dirs:
        Path(dir_name).mkdir(parents=True, exist_ok=True)
        print(f"   ✅ {dir_name}/")
    
    return True


def setup_database():
    """Initialize database."""
    print("\n🗄️  Setting up database...")
    
    try:
        # Import here to avoid issues if dependencies not installed
        sys.path.insert(0, str(Path("src").absolute()))
        from database import init_db
        
        init_db()
        print("✅ Database initialized successfully")
        return True
    except Exception as e:
        print(f"⚠️  Database initialization skipped: {e}")
        print("   You can initialize the database later by running:")
        print("   python -c \"from src.database import init_db; init_db()\"")
        return False


def setup_gmail_auth():
    """Setup Gmail OAuth2 authentication."""
    print("\n📧 Gmail OAuth2 Setup (Optional)")
    print("   To enable email processing, you need to:")
    print("   1. Go to https://console.cloud.google.com/")
    print("   2. Create a project and enable Gmail API")
    print("   3. Download credentials.json and save to config/credentials.json")
    print("   4. Run: python src/gmail/token_manager.py auth")
    
    response = input("\n   Have you already set up Gmail credentials? (y/N): ").lower()
    if response == 'y':
        print("   ✅ Gmail setup skipped (already configured)")
    else:
        print("   ℹ️  You can configure Gmail later")
    
    return True


def setup_ollama():
    """Check Ollama setup."""
    print("\n🤖 Ollama AI Setup")
    print("   PlantMind AI requires Ollama running locally.")
    
    # Check if Ollama is installed
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"   ✅ Ollama found: {result.stdout.strip()}")
            
            # Check if required models are available
            print("\n   Checking required models...")
            models_result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True
            )
            
            required_models = ["phi3:mini", "mistral"]
            for model in required_models:
                if model in models_result.stdout:
                    print(f"   ✅ {model} available")
                else:
                    print(f"   ⚠️  {model} not found. Pull with: ollama pull {model}")
            
            return True
    except FileNotFoundError:
        pass
    
    print("   ⚠️  Ollama not found in PATH")
    print("   Please install Ollama from https://ollama.com")
    print("   Then pull required models:")
    print("     ollama pull phi3:mini")
    print("     ollama pull mistral")
    
    return False


def create_systemd_service():
    """Create systemd service file (Linux only)."""
    if os.name != 'posix':
        return True
    
    print("\n🔧 Systemd Service Setup (Optional)")
    response = input("   Create systemd service for auto-start? (y/N): ").lower()
    
    if response != 'y':
        return True
    
    service_content = """[Unit]
Description=PlantMind AI - Smart Factory System
After=network.target postgresql.service

[Service]
Type=simple
User=plantmind
WorkingDirectory=/opt/plantmind
Environment=PATH=/opt/plantmind/venv/bin
ExecStart=/opt/plantmind/venv/bin/python -m src.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    service_path = Path("plantmind.service")
    with open(service_path, 'w') as f:
        f.write(service_content)
    
    print(f"   ✅ Service file created: {service_path}")
    print("   To install system-wide:")
    print(f"   sudo cp {service_path} /etc/systemd/system/")
    print("   sudo systemctl enable plantmind")
    print("   sudo systemctl start plantmind")
    
    return True


def run_tests():
    """Run test suite."""
    print("\n🧪 Running tests...")
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ All tests passed!")
            return True
        else:
            print("⚠️  Some tests failed")
            print(result.stdout)
            print(result.stderr)
            return False
    except Exception as e:
        print(f"⚠️  Could not run tests: {e}")
        return False


def print_completion_message():
    """Print setup completion message."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                     ✅ Setup Complete!                         ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Next steps:                                                 ║
║  1. Review and edit .env file with your settings            ║
║  2. Ensure PostgreSQL is running                             ║
║  3. Ensure Ollama is running with required models            ║
║  4. Run: python src/main.py                                  ║
║                                                              ║
║  Access the application at: http://localhost:8000            ║
║  Default login: office / office123                           ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")


def main():
    """Main setup function."""
    parser = argparse.ArgumentParser(description="PlantMind AI Setup")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")
    parser.add_argument("--production", action="store_true", help="Production setup mode")
    args = parser.parse_args()
    
    print_banner()
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Create virtual environment
    venv_path = None
    if not args.production:
        venv_path = create_virtual_environment()
        if venv_path:
            print(f"\n   Activate virtual environment:")
            if os.name == 'nt':
                print(f"   {venv_path}\\Scripts\\activate")
            else:
                print(f"   source {venv_path}/bin/activate")
    
    # Install dependencies
    if not install_dependencies(venv_path):
        print("\n❌ Setup failed: Could not install dependencies")
        sys.exit(1)
    
    # Setup environment file
    if not setup_environment_file():
        print("\n⚠️  Environment setup skipped")
    
    # Create directories
    create_directories()
    
    # Setup Gmail
    setup_gmail_auth()
    
    # Setup Ollama
    setup_ollama()
    
    # Initialize database
    setup_database()
    
    # Create systemd service (Linux only)
    if args.production:
        create_systemd_service()
    
    # Run tests
    if not args.skip_tests:
        run_tests()
    
    print_completion_message()


if __name__ == "__main__":
    main()
