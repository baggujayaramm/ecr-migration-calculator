import boto3
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def write_output(file, text):
    """Write to both console and file"""
    print(text)
    file.write(text + "\n")

def calculate_migration_time():
    """
    Calculate time needed to migrate ECR repositories where:
    1. Repository has images pushed within the date range
    2. Repository has NOT been pulled in the last 1 year (365 days)
    Migration speed: 1.33 MB/s
    """
    
    # Get AWS credentials from .env file
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    repository_name = os.getenv('ECR_REPOSITORY_NAME')  # Optional: specific repo or ALL repos
    
    # Get date range from .env
    start_date_str = os.getenv('START_DATE')  # Format: YYYY-MM-DD
    end_date_str = os.getenv('END_DATE')      # Format: YYYY-MM-DD
    
    # Validate inputs
    if not all([aws_access_key, aws_secret_key]):
        print("Error: Missing required credentials in .env file")
        return
    
    # Convert dates to datetime objects
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    except (ValueError, TypeError) as e:
        print(f"Error: Invalid date format. Use YYYY-MM-DD. Error: {e}")
        return
    
    # Calculate cutoff date for "not pulled in last 1 year"
    one_year_ago = datetime.now() - timedelta(days=365)
    
    # Create output filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"ecr_migration_report_{timestamp}.txt"
    
    # Open output file
    with open(output_filename, 'w', encoding='utf-8') as output_file:
        
        # Create ECR client
        ecr_client = boto3.client(
            'ecr',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region
        )
        
        # Write header
        write_output(output_file, "=" * 70)
        write_output(output_file, "ECR MIGRATION TIME CALCULATION REPORT")
        write_output(output_file, "=" * 70)
        write_output(output_file, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        write_output(output_file, f"AWS Region: {aws_region}")
        if repository_name:
            write_output(output_file, f"Target: Single repository '{repository_name}'")
        else:
            write_output(output_file, f"Target: ALL repositories")
        write_output(output_file, f"Build date range: {start_date_str} to {end_date_str}")
        write_output(output_file, f"Migration criteria: Repositories NOT pulled since {one_year_ago.date()}")
        write_output(output_file, "=" * 70)
        write_output(output_file, "")
        
        total_size_bytes = 0
        total_image_count = 0
        repositories_to_migrate = 0
        repositories_skipped = 0
        repositories_processed = 0
        skipped_repos_details = []  # Store details of skipped repositories
        
        try:
            # Get repositories to scan
            repositories_to_scan = []
            
            if repository_name:
                # Scan only the specified repository
                try:
                    response = ecr_client.describe_repositories(repositoryNames=[repository_name])
                    repositories_to_scan = response['repositories']
                except ecr_client.exceptions.RepositoryNotFoundException:
                    error_msg = f"Error: Repository '{repository_name}' not found"
                    write_output(output_file, error_msg)
                    return
            else:
                # Get all repositories
                repo_paginator = ecr_client.get_paginator('describe_repositories')
                repo_pages = repo_paginator.paginate()
                
                for repo_page in repo_pages:
                    repositories_to_scan.extend(repo_page['repositories'])
            
            for repository in repositories_to_scan:
                repo_name = repository['repositoryName']
                repositories_processed += 1
                
                write_output(output_file, f"\n[Repository: {repo_name}]")
                write_output(output_file, "-" * 70)
                
                repo_image_count = 0
                repo_size_bytes = 0
                repo_should_migrate = True
                repo_last_pull = None
                images_in_date_range = []
                
                try:
                    # Get all images from this repository
                    image_paginator = ecr_client.get_paginator('describe_images')
                    image_pages = image_paginator.paginate(repositoryName=repo_name)
                    
                    # First pass: check if repository was pulled recently
                    for image_page in image_pages:
                        for image in image_page['imageDetails']:
                            last_pulled = image.get('lastRecordedPullTime')
                            
                            # Track the most recent pull in the entire repository
                            if last_pulled:
                                if repo_last_pull is None or last_pulled > repo_last_pull:
                                    repo_last_pull = last_pulled
                            
                            # Collect images within date range
                            push_date = image['imagePushedAt']
                            if start_date <= push_date.replace(tzinfo=None) <= end_date:
                                images_in_date_range.append(image)
                    
                    # Check if repository should be migrated
                    if repo_last_pull is None:
                        repo_should_migrate = True
                        pull_status = "Never pulled - WILL MIGRATE"
                    elif repo_last_pull.replace(tzinfo=None) < one_year_ago:
                        repo_should_migrate = True
                        pull_status = f"Last pulled: {repo_last_pull.date()} - WILL MIGRATE"
                    else:
                        repo_should_migrate = False
                        pull_status = f"Recently pulled: {repo_last_pull.date()} - SKIPPED"
                        repositories_skipped += 1
                        
                        # Store skipped repository details
                        skipped_repos_details.append({
                            'name': repo_name,
                            'last_pull': repo_last_pull.date(),
                            'images_count': len(images_in_date_range)
                        })
                    
                    write_output(output_file, f"  Status: {pull_status}")
                    write_output(output_file, f"  Images in date range: {len(images_in_date_range)}")
                    
                    # If repository should be migrated, process all images in date range
                    if repo_should_migrate and len(images_in_date_range) > 0:
                        repositories_to_migrate += 1
                        write_output(output_file, f"  Images to migrate:")
                        
                        for image in images_in_date_range:
                            image_size = image['imageSizeInBytes']
                            repo_size_bytes += image_size
                            repo_image_count += 1
                            
                            tags = image.get('imageTags', ['<untagged>'])
                            size_mb = image_size / (1024 * 1024)
                            push_date = image['imagePushedAt']
                            write_output(output_file, f"    [MIGRATE] {tags[0]:<40} {size_mb:>8.2f} MB  {push_date.date()}")
                        
                        # Update totals
                        total_size_bytes += repo_size_bytes
                        total_image_count += repo_image_count
                        
                        repo_size_mb = repo_size_bytes / (1024 * 1024)
                        write_output(output_file, f"  Repository total: {repo_image_count} images, {repo_size_mb:.2f} MB")
                    elif not repo_should_migrate and len(images_in_date_range) > 0:
                        write_output(output_file, f"  [SKIP] Skipping all {len(images_in_date_range)} images (repository pulled recently)")
                    else:
                        write_output(output_file, f"  No images found in date range")
                
                except Exception as e:
                    write_output(output_file, f"  Error processing repository: {e}")
            
            # Calculate total size in different units
            total_size_mb = total_size_bytes / (1024 * 1024)
            total_size_gb = total_size_mb / 1024
            
            # Calculate migration time at 1.33 MB/s
            speed_mb_per_sec = 1.33
            time_seconds = total_size_mb / speed_mb_per_sec if total_size_mb > 0 else 0
            time_minutes = time_seconds / 60
            time_hours = time_minutes / 60
            
            # Display final results
            write_output(output_file, "\n" + "=" * 70)
            write_output(output_file, "COMPLETE MIGRATION SUMMARY")
            write_output(output_file, "=" * 70)
            write_output(output_file, f"Total repositories scanned: {repositories_processed}")
            write_output(output_file, f"Repositories to migrate: {repositories_to_migrate}")
            write_output(output_file, f"Repositories skipped (pulled recently): {repositories_skipped}")
            write_output(output_file, f"Total images to migrate: {total_image_count}")
            write_output(output_file, f"Total migration size: {total_size_mb:.2f} MB ({total_size_gb:.2f} GB)")
            write_output(output_file, f"\nMigration speed: {speed_mb_per_sec} MB/s")
            
            if total_image_count > 0:
                write_output(output_file, f"\nEstimated migration time:")
                write_output(output_file, f"  - {time_seconds:.2f} seconds")
                write_output(output_file, f"  - {time_minutes:.2f} minutes")
                write_output(output_file, f"  - {time_hours:.2f} hours")
                
                if time_hours >= 24:
                    time_days = time_hours / 24
                    write_output(output_file, f"  - {time_days:.2f} days")
            else:
                write_output(output_file, "\n[OK] No images to migrate!")
            
            # Add detailed skipped repositories section
            if len(skipped_repos_details) > 0:
                write_output(output_file, "\n" + "=" * 70)
                write_output(output_file, "SKIPPED REPOSITORIES DETAILS")
                write_output(output_file, "=" * 70)
                write_output(output_file, f"Total skipped: {len(skipped_repos_details)}")
                write_output(output_file, "Reason: Recently pulled (within last 1 year)")
                write_output(output_file, "")
                
                for repo in skipped_repos_details:
                    write_output(output_file, f"Repository: {repo['name']}")
                    write_output(output_file, f"  Last pulled: {repo['last_pull']}")
                    write_output(output_file, f"  Images in date range: {repo['images_count']}")
                    write_output(output_file, "")
            
            write_output(output_file, "=" * 70)
            write_output(output_file, f"\nReport saved to: {output_filename}")
            print(f"\n*** Full report saved to: {output_filename} ***")
            
        except Exception as e:
            error_msg = f"Error accessing ECR: {e}"
            write_output(output_file, error_msg)

if __name__ == "__main__":
    calculate_migration_time()