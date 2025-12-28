import boto3
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def write_output(file, text):
    """Write to both console and file"""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('utf-8', errors='replace').decode('utf-8', errors='replace'))
    file.write(text + "\n")

def format_size(bytes_value):
    """Convert bytes to human-readable format"""
    mb = bytes_value / (1024 * 1024)
    gb = mb / 1024
    if gb >= 1:
        return f"{gb:.2f} GB"
    return f"{mb:.2f} MB"

def calculate_migration_time():
    """
    Calculate migration time for ECR images where:
    - Last pulled timestamp is between START_DATE and END_DATE (inclusive)
    - Never pulled images use creation/push date as their last pulled date
    Migration speed: 1.33 MB/s
    """
    
    # Get AWS credentials from .env file
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    repository_name = os.getenv('ECR_REPOSITORY_NAME')
    
    # Get date range from .env
    start_date_str = os.getenv('START_DATE')  # Format: YYYY-MM-DD
    end_date_str = os.getenv('END_DATE')      # Format: YYYY-MM-DD
    
    # Validate inputs
    if not all([aws_access_key, aws_secret_key]):
        print("Error: Missing required credentials in .env file")
        return
    
    if not all([start_date_str, end_date_str]):
        print("Error: Missing START_DATE or END_DATE in .env file")
        return
    
    # Convert dates to datetime objects
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        # Set end_date to end of day for inclusive comparison
        end_date = end_date.replace(hour=23, minute=59, second=59)
    except (ValueError, TypeError) as e:
        print(f"Error: Invalid date format. Use YYYY-MM-DD. Error: {e}")
        return
    
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
        write_output(output_file, "")
        write_output(output_file, "+" + "=" * 78 + "+")
        write_output(output_file, "|" + " " * 78 + "|")
        write_output(output_file, "|" + "ECR TO S3 MIGRATION TIME CALCULATOR".center(78) + "|")
        write_output(output_file, "|" + " " * 78 + "|")
        write_output(output_file, "+" + "=" * 78 + "+")
        write_output(output_file, "")
        write_output(output_file, "  Report Generated : " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        write_output(output_file, "  AWS Region       : " + aws_region)
        if repository_name:
            write_output(output_file, "  Target Scope     : Single Repository '" + repository_name + "'")
        else:
            write_output(output_file, "  Target Scope     : All Repositories")
        write_output(output_file, "")
        write_output(output_file, "  MIGRATION CRITERIA")
        write_output(output_file, "  " + "-" * 40)
        write_output(output_file, "  Last Pulled Between : " + start_date_str + " to " + end_date_str)
        write_output(output_file, "  (Images last pulled/created within this date range will be migrated)")
        write_output(output_file, "")
        write_output(output_file, "-" * 80)
        write_output(output_file, "")
        
        total_size_bytes = 0
        total_images_to_migrate = 0
        total_images_scanned = 0
        repositories_processed = 0
        repositories_with_migrations = 0
        
        migration_details = []
        
        try:
            # Get repositories to scan
            repositories_to_scan = []
            
            if repository_name:
                try:
                    response = ecr_client.describe_repositories(repositoryNames=[repository_name])
                    repositories_to_scan = response['repositories']
                except ecr_client.exceptions.RepositoryNotFoundException:
                    error_msg = f"ERROR: Repository '{repository_name}' not found"
                    write_output(output_file, error_msg)
                    return
            else:
                repo_paginator = ecr_client.get_paginator('describe_repositories')
                repo_pages = repo_paginator.paginate()
                
                for repo_page in repo_pages:
                    repositories_to_scan.extend(repo_page['repositories'])
            
            # Process each repository
            for repository in repositories_to_scan:
                repo_name = repository['repositoryName']
                repositories_processed += 1
                
                repo_migrate_count = 0
                repo_migrate_size = 0
                
                write_output(output_file, "+-- REPOSITORY: " + repo_name)
                write_output(output_file, "|")
                
                try:
                    # Get all images from this repository
                    image_paginator = ecr_client.get_paginator('describe_images')
                    image_pages = image_paginator.paginate(repositoryName=repo_name)
                    
                    repo_images = []
                    for image_page in image_pages:
                        repo_images.extend(image_page['imageDetails'])
                    
                    if len(repo_images) == 0:
                        write_output(output_file, "|  [INFO] No images found in this repository")
                        write_output(output_file, "|")
                        write_output(output_file, "+" + "-" * 79)
                        write_output(output_file, "")
                        continue
                    
                    total_images_scanned += len(repo_images)
                    write_output(output_file, "|  Total images in repository: " + str(len(repo_images)))
                    write_output(output_file, "|")
                    
                    # Evaluate each image
                    for image in repo_images:
                        image_size = image['imageSizeInBytes']
                        tags = image.get('imageTags', ['<untagged>'])
                        tag_name = tags[0] if tags else '<untagged>'
                        push_date = image['imagePushedAt']
                        last_pulled = image.get('lastRecordedPullTime')
                        
                        push_str = push_date.strftime('%Y-%m-%d')
                        size_str = format_size(image_size)
                        
                        # Use last pulled time, or fall back to push date if never pulled
                        effective_pull_date = last_pulled if last_pulled else push_date
                        effective_pull_date = effective_pull_date.replace(tzinfo=None)
                        
                        # Check if effective pull date is in range
                        if start_date <= effective_pull_date <= end_date:
                            # MIGRATE - last pulled/created in date range
                            repo_migrate_count += 1
                            repo_migrate_size += image_size
                            total_images_to_migrate += 1
                            total_size_bytes += image_size
                            
                            pulled_str = effective_pull_date.strftime('%Y-%m-%d')
                            
                            # Indicate if this was never actually pulled
                            pull_status = "Created" if not last_pulled else "Last pulled"
                            
                            write_output(output_file, f"|  >> MIGRATE >> {tag_name:<30} {size_str:>10}  {pull_status}: {pulled_str}")
                            
                            migration_details.append({
                                'repo': repo_name,
                                'tag': tag_name,
                                'size': image_size,
                                'last_pulled': pulled_str,
                                'push_date': push_str,
                                'never_pulled': not last_pulled
                            })
                    
                    # Repository summary
                    write_output(output_file, "|")
                    if repo_migrate_count > 0:
                        repositories_with_migrations += 1
                        write_output(output_file, f"|  Repository Summary: {repo_migrate_count} to migrate ({format_size(repo_migrate_size)})")
                    else:
                        write_output(output_file, "|  Repository Summary: No images qualify for migration")
                    
                except Exception as e:
                    write_output(output_file, f"|  [ERROR] Failed to process repository: {e}")
                
                write_output(output_file, "|")
                write_output(output_file, "+" + "-" * 79)
                write_output(output_file, "")
            
            # Calculate migration time at 1.33 MB/s
            speed_mb_per_sec = 1.33
            total_size_mb = total_size_bytes / (1024 * 1024)
            time_seconds = total_size_mb / speed_mb_per_sec if total_size_mb > 0 else 0
            time_minutes = time_seconds / 60
            time_hours = time_minutes / 60
            time_days = time_hours / 24
            
            # Final Summary
            write_output(output_file, "")
            write_output(output_file, "+" + "=" * 78 + "+")
            write_output(output_file, "|" + " " * 78 + "|")
            write_output(output_file, "|" + "MIGRATION SUMMARY".center(78) + "|")
            write_output(output_file, "|" + " " * 78 + "|")
            write_output(output_file, "+" + "=" * 78 + "+")
            write_output(output_file, "")
            write_output(output_file, "  Repositories")
            write_output(output_file, "  " + "-" * 40)
            write_output(output_file, f"    Total analyzed               : {repositories_processed}")
            write_output(output_file, f"    With migration candidates    : {repositories_with_migrations}")
            write_output(output_file, "")
            write_output(output_file, "  Images Analysis")
            write_output(output_file, "  " + "-" * 40)
            write_output(output_file, f"    Total scanned                : {total_images_scanned}")
            write_output(output_file, f"    Images to MIGRATE            : {total_images_to_migrate}")
            write_output(output_file, f"    Migration percentage         : {(total_images_to_migrate/total_images_scanned*100) if total_images_scanned > 0 else 0:.1f}%")
            write_output(output_file, "")
            write_output(output_file, "  Migration Size")
            write_output(output_file, "  " + "-" * 40)
            write_output(output_file, f"    Total data to migrate        : {format_size(total_size_bytes)}")
            write_output(output_file, "")
            
            if total_images_to_migrate > 0:
                write_output(output_file, "  ESTIMATED MIGRATION TIME (at 1.33 MB/s)")
                write_output(output_file, "  " + "-" * 40)
                write_output(output_file, f"    {time_seconds:,.0f} seconds")
                write_output(output_file, f"    {time_minutes:,.1f} minutes")
                write_output(output_file, f"    {time_hours:,.2f} hours")
                if time_hours >= 24:
                    write_output(output_file, f"    {time_days:,.2f} days")
                write_output(output_file, "")
            else:
                write_output(output_file, "  [RESULT] No images found with pull/creation dates in the specified range")
                write_output(output_file, "")
            
            # Top 10 largest migrations
            if len(migration_details) > 0:
                write_output(output_file, "")
                write_output(output_file, "+" + "=" * 78 + "+")
                write_output(output_file, "|" + " " * 78 + "|")
                write_output(output_file, "|" + "TOP 10 LARGEST MIGRATIONS".center(78) + "|")
                write_output(output_file, "|" + " " * 78 + "|")
                write_output(output_file, "+" + "=" * 78 + "+")
                write_output(output_file, "")
                
                sorted_migrations = sorted(migration_details, key=lambda x: x['size'], reverse=True)[:10]
                
                for idx, img in enumerate(sorted_migrations, 1):
                    never_pulled_tag = " [Never Pulled]" if img['never_pulled'] else ""
                    write_output(output_file, f"  {idx:2d}. {img['repo']}/{img['tag']}{never_pulled_tag}")
                    write_output(output_file, f"      Size: {format_size(img['size'])}  |  Date: {img['last_pulled']}")
                    write_output(output_file, "")
            
            write_output(output_file, "")
            write_output(output_file, "=" * 80)
            write_output(output_file, "  Report saved to: " + output_filename)
            write_output(output_file, "=" * 80)
            print(f"\n*** Report successfully saved to: {output_filename} ***")
            
        except Exception as e:
            error_msg = f"ERROR: Failed to access ECR: {e}"
            write_output(output_file, error_msg)

if __name__ == "__main__":
    calculate_migration_time()