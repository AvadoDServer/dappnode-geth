#!/usr/bin/env python3
"""
Script to automatically update Geth upstream version and package version.

This script:
1. Fetches the latest release from ethereum/go-ethereum
2. Compares it with the current upstream version in build/dappnode_package-mainnet.json
3. If a newer version is found:
   - Increments the patch version in dappnode_package-mainnet.json
   - Updates the upstream version in dappnode_package-mainnet.json
   - Updates the image tag in docker-compose-mainnet.yml
   - Updates the VERSION build arg in docker-compose-mainnet.yml

Note: Only mainnet files are updated by this script.
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
            
            # Ensure the tag has 'v' prefix for consistency
            if tag_name and not tag_name.startswith('v'):
                tag_name = 'v' + tag_name
            
            return tag_name
    except urllib.error.HTTPError as e:
        if e.code == 403:
            print(f"Error fetching latest release: Rate limit exceeded (HTTP 403)")
            print(f"Tip: Ensure GITHUB_TOKEN is set and has sufficient quota")
        else:
            print(f"Error fetching latest release: HTTP {e.code} - {e.reason}")
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
    # Pattern: VERSION: vX.Y.Z or VERSION: X.Y.Z
    # Ensure the new version has 'v' prefix
    version_with_v = new_version_arg if new_version_arg.startswith('v') else 'v' + new_version_arg
    content = re.sub(
        r"(VERSION:\s+)v?[\d.]+",
        rf"\g<1>{version_with_v}",
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
    
    # Only update mainnet files
    mainnet_package = build_dir / 'dappnode_package-mainnet.json'
    mainnet_compose = build_dir / 'docker-compose-mainnet.yml'
    
    if not mainnet_package.exists():
        print(f"Error: {mainnet_package} not found")
        sys.exit(1)
    
    if not mainnet_compose.exists():
        print(f"Error: {mainnet_compose} not found")
        sys.exit(1)
    
    print("Updating mainnet package file...")
    
    # Calculate new version
    new_pkg_version = increment_patch_version(current_version)
    
    # Update package JSON
    update_package_json(mainnet_package, new_pkg_version, latest_geth_version)
    
    print("\nUpdating mainnet docker-compose file...")
    
    # Update docker-compose
    update_docker_compose(mainnet_compose, new_pkg_version, latest_geth_version)
    
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
            f.write(f"new_package_version={new_pkg_version}\n")
    
    print("\nSummary:")
    print(f"  Geth version: {current_upstream} -> {latest_geth_version}")
    print(f"  Package version: {current_version} -> {new_pkg_version}")
    print(f"  Files updated: mainnet only")


if __name__ == '__main__':
    main()
