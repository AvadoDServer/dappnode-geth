#!/usr/bin/env python3
"""
Script to automatically update Geth upstream version and package version.

This script:
1. Fetches the latest release from ethereum/go-ethereum
2. Compares it with the current upstream version in build/dappnode_package-mainnet.json
3. If a newer version is found:
   - Increments the patch version in all dappnode_package-*.json files
   - Updates the upstream version in all dappnode_package-*.json files
   - Updates the image tag in all docker-compose-*.yml files
   - Updates the VERSION build arg in all docker-compose-*.yml files
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import urllib.request
import urllib.error


def fetch_latest_geth_release() -> str:
    """
    Fetch the latest release tag from ethereum/go-ethereum repository.
    
    Returns:
        str: The latest release tag (e.g., "v1.16.9")
    """
    api_url = "https://api.github.com/repos/ethereum/go-ethereum/releases/latest"
    
    try:
        req = urllib.request.Request(api_url)
        req.add_header('Accept', 'application/vnd.github+json')
        
        # Add GitHub token if available for authentication
        github_token = os.environ.get('GITHUB_TOKEN')
        if github_token:
            req.add_header('Authorization', f'Bearer {github_token}')
        
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            tag_name = data.get('tag_name', '')
            print(f"Latest Geth release: {tag_name}")
            return tag_name
    except urllib.error.HTTPError as e:
        print(f"Error fetching latest release: {e}")
        print(f"Tip: Set GITHUB_TOKEN environment variable to avoid rate limiting")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


def parse_version(version_str: str) -> Tuple[int, int, int]:
    """
    Parse a version string into major, minor, patch components.
    
    Args:
        version_str: Version string like "10.0.78" or "v1.16.8"
    
    Returns:
        Tuple of (major, minor, patch)
    """
    # Remove 'v' prefix if present
    clean_version = version_str.lstrip('v')
    parts = clean_version.split('.')
    
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {version_str}")
    
    return int(parts[0]), int(parts[1]), int(parts[2])


def increment_patch_version(version_str: str) -> str:
    """
    Increment the patch version of a semver string.
    
    Args:
        version_str: Version string like "10.0.78"
    
    Returns:
        Incremented version string like "10.0.79"
    """
    major, minor, patch = parse_version(version_str)
    return f"{major}.{minor}.{patch + 1}"


def compare_versions(v1: str, v2: str) -> int:
    """
    Compare two version strings.
    
    Args:
        v1: First version string
        v2: Second version string
    
    Returns:
        -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2
    """
    major1, minor1, patch1 = parse_version(v1)
    major2, minor2, patch2 = parse_version(v2)
    
    if (major1, minor1, patch1) < (major2, minor2, patch2):
        return -1
    elif (major1, minor1, patch1) == (major2, minor2, patch2):
        return 0
    else:
        return 1


def update_package_json(file_path: Path, new_version: str, new_upstream: str) -> None:
    """
    Update a dappnode_package-*.json file with new version and upstream.
    
    Args:
        file_path: Path to the JSON file
        new_version: New package version
        new_upstream: New upstream Geth version
    """
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    old_version = data.get('version', '')
    old_upstream = data.get('upstream', '')
    
    data['version'] = new_version
    data['upstream'] = new_upstream
    
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')  # Add trailing newline
    
    print(f"Updated {file_path.name}: version {old_version} -> {new_version}, upstream {old_upstream} -> {new_upstream}")


def update_docker_compose(file_path: Path, new_image_tag: str, new_version_arg: str) -> None:
    """
    Update a docker-compose-*.yml file with new image tag and VERSION build arg.
    
    Args:
        file_path: Path to the docker-compose file
        new_image_tag: New image tag (package version)
        new_version_arg: New VERSION build argument (Geth version)
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Update image tag
    # Pattern: image: 'service-name:version'
    content = re.sub(
        r"(image:\s+['\"][\w.-]+\.(?:public\.dappnode|avado\.dnp\.dappnode)\.eth:)[^'\"]+(['\"])",
        rf"\g<1>{new_image_tag}\g<2>",
        content
    )
    
    # Update VERSION build arg
    # Pattern: VERSION: vX.Y.Z
    content = re.sub(
        r"(VERSION:\s+)v[\d.]+",
        rf"\g<1>{new_version_arg}",
        content
    )
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"Updated {file_path.name}: image tag -> {new_image_tag}, VERSION -> {new_version_arg}")


def main():
    """Main execution function."""
    # Get the repository root (3 levels up from this script)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent.parent
    build_dir = repo_root / 'build'
    
    print("=" * 60)
    print("Geth Upstream Version Update Script")
    print("=" * 60)
    
    # Fetch latest Geth release
    latest_geth_version = fetch_latest_geth_release()
    
    if not latest_geth_version:
        print("Error: Could not fetch latest Geth release")
        sys.exit(1)
    
    # Read current upstream version from mainnet package
    mainnet_package_path = build_dir / 'dappnode_package-mainnet.json'
    
    if not mainnet_package_path.exists():
        print(f"Error: {mainnet_package_path} not found")
        sys.exit(1)
    
    with open(mainnet_package_path, 'r') as f:
        mainnet_data = json.load(f)
    
    current_upstream = mainnet_data.get('upstream', '')
    current_version = mainnet_data.get('version', '')
    
    print(f"Current upstream version: {current_upstream}")
    print(f"Current package version: {current_version}")
    print(f"Latest Geth version: {latest_geth_version}")
    
    # Compare versions
    if compare_versions(current_upstream, latest_geth_version) >= 0:
        print("No update needed. Current version is up to date or newer.")
        # Set output for GitHub Actions (no update)
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write(f"update_available=false\n")
        sys.exit(0)
    
    print("\n" + "=" * 60)
    print(f"Update available: {current_upstream} -> {latest_geth_version}")
    print("=" * 60 + "\n")
    
    # Find all package JSON files
    package_files = sorted(build_dir.glob('dappnode_package-*.json'))
    
    if not package_files:
        print("Error: No dappnode_package-*.json files found")
        sys.exit(1)
    
    print(f"Found {len(package_files)} package files to update")
    
    # Update each package file
    for package_file in package_files:
        # Read current version from this specific file
        with open(package_file, 'r') as f:
            pkg_data = json.load(f)
        
        current_pkg_version = pkg_data.get('version', '')
        new_pkg_version = increment_patch_version(current_pkg_version)
        
        update_package_json(package_file, new_pkg_version, latest_geth_version)
    
    # Find all docker-compose YAML files
    compose_files = sorted(build_dir.glob('docker-compose-*.yml'))
    
    if not compose_files:
        print("Error: No docker-compose-*.yml files found")
        sys.exit(1)
    
    print(f"\nFound {len(compose_files)} docker-compose files to update")
    
    # For docker-compose files, we need to match each with its corresponding package
    for compose_file in compose_files:
        # Extract network name from filename (e.g., docker-compose-mainnet.yml -> mainnet)
        network_name = compose_file.stem.replace('docker-compose-', '')
        
        # Find corresponding package file
        package_file = build_dir / f'dappnode_package-{network_name}.json'
        
        if not package_file.exists():
            print(f"Warning: No matching package file for {compose_file.name}, skipping")
            continue
        
        # Read the new version from the package file
        with open(package_file, 'r') as f:
            pkg_data = json.load(f)
        
        new_pkg_version = pkg_data.get('version', '')
        
        update_docker_compose(compose_file, new_pkg_version, latest_geth_version)
    
    print("\n" + "=" * 60)
    print("Update completed successfully!")
    print("=" * 60)
    
    # Set outputs for GitHub Actions
    if 'GITHUB_OUTPUT' in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"update_available=true\n")
            f.write(f"old_version={current_upstream}\n")
            f.write(f"new_version={latest_geth_version}\n")
            f.write(f"old_package_version={current_version}\n")
            
            # Get the new package version from mainnet
            with open(mainnet_package_path, 'r') as pf:
                updated_data = json.load(pf)
                new_package_version = updated_data.get('version', '')
            
            f.write(f"new_package_version={new_package_version}\n")
    
    print("\nSummary:")
    print(f"  Geth version: {current_upstream} -> {latest_geth_version}")
    print(f"  Package files updated: {len(package_files)}")
    print(f"  Docker-compose files updated: {len(compose_files)}")


if __name__ == '__main__':
    main()
