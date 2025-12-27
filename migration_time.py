import boto3
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def write_output(file, text):
    """Write to both console and file"""
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback for Windows console encoding issues
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
    Calculate time needed to migrate ECR images where:
    1. Image was pushed within the date range
    2. Image has NOT been pulled in the last 1 year (365 days)
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
        write_output(output_file, "")
        write_output(output_file, "+" + "=" * 78 + "+")
        write_output(output_file, "|" + " " * 78 + "|")
        write_output(output_file, "|" + "       ECR TO S3 MIGRATION ANALYSIS REPORT".center(78) + "|")
        write_output(output_file, "|" + " " * 78 + "|")
        write_output(output_file, "+" + "=" * 78 + "+")
        write_output(output_file, "")
        write_output(output_file, "  Report Generated : " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        write_output(output_file, "  AWS Region       : " + aws_region)
        if repository_name:
            write_output(output_file, "  Target Scope     : Single Repository '" + repository_name + "'")
        else:
            write_output(output_file, "  Target Scope     : All Repositories")
        write_output(output_file, "  Build Date Range : " + start_date_str + " to " + end_date_str)
        write_output(output_file, "  Migration Rule   : Images NOT pulled since " + one_year_ago.strftime('%Y-%m-%d'))
        write_output(output_file, "")
        write_output(output_file, "-" * 80)
        write_output(output_file, "")
        
        total_size_bytes = 0
        total_images_to_migrate = 0
        total_images_to_keep = 0
        repositories_processed = 0
        repositories_with_migrations = 0
        
        migration_details = []  # Store details for summary
        kept_details = []       # Store details for kept images
        
        try:
            # Get repositories to scan
            repositories_to_scan = []
            
            if repository_name:
                # Scan only the specified repository
                try:
                    response = ecr_client.describe_repositories(repositoryNames=[repository_name])
                    repositories_to_scan = response['repositories']
                except ecr_client.exceptions.RepositoryNotFoundException:
                    error_msg = f"ERROR: Repository '{repository_name}' not found"
                    write_output(output_file, error_msg)
                    return
            else:
                # Get all repositories
                repo_paginator = ecr_client.get_paginator('describe_repositories')
                repo_pages = repo_paginator.paginate()
                
                for repo_page in repo_pages:
                    repositories_to_scan.extend(repo_page['repositories'])
            
            # Process each repository
            for repository in repositories_to_scan:
                repo_name = repository['repositoryName']
                repositories_processed += 1
                
                repo_migrate_count = 0
                repo_keep_count = 0
                repo_migrate_size = 0
                
                write_output(output_file, "+-- REPOSITORY: " + repo_name)
                write_output(output_file, "|")
                
                try:
                    # Get all images from this repository
                    image_paginator = ecr_client.get_paginator('describe_images')
                    image_pages = image_paginator.paginate(repositoryName=repo_name)
                    
                    images_in_date_range = []
                    
                    # Collect images within date range
                    for image_page in image_pages:
                        for image in image_page['imageDetails']:
                            push_date = image['imagePushedAt']
                            if start_date <= push_date.replace(tzinfo=None) <= end_date:
                                images_in_date_range.append(image)
                    
                    if len(images_in_date_range) == 0:
                        write_output(output_file, "|  [INFO] No images found in specified date range")
                        write_output(output_file, "|")
                        write_output(output_file, "+" + "-" * 79)
                        write_output(output_file, "")
                        continue
                    
                    write_output(output_file, "|  Images in date range: " + str(len(images_in_date_range)))
                    write_output(output_file, "|")
                    
                    # Evaluate EACH image individually
                    for image in images_in_date_range:
                        image_size = image['imageSizeInBytes']
                        tags = image.get('imageTags', ['<untagged>'])
                        tag_name = tags[0] if tags else '<untagged>'
                        push_date = image['imagePushedAt']
                        last_pulled = image.get('lastRecordedPullTime')
                        
                        # Decision logic for THIS specific image
                        should_migrate = False
                        status_reason = ""
                        
                        if last_pulled is None:
                            should_migrate = True
                            status_reason = "Never pulled"
                        elif last_pulled.replace(tzinfo=None) < one_year_ago:
                            should_migrate = True
                            days_since_pull = (datetime.now() - last_pulled.replace(tzinfo=None)).days
                            status_reason = f"Last pulled {days_since_pull} days ago"
                        else:
                            should_migrate = False
                            days_since_pull = (datetime.now() - last_pulled.replace(tzinfo=None)).days
                            status_reason = f"Pulled {days_since_pull} days ago (recent)"
                        
                        # Format output line
                        size_str = format_size(image_size)
                        push_str = push_date.strftime('%Y-%m-%d')
                        
                        if should_migrate:
                            # MIGRATE to S3
                            repo_migrate_count += 1
                            repo_migrate_size += image_size
                            total_images_to_migrate += 1
                            total_size_bytes += image_size
                            
                            write_output(output_file, f"|  >> MIGRATE >> {tag_name:<35} {size_str:>10}  Pushed: {push_str}  ({status_reason})")
                            
                            migration_details.append({
                                'repo': repo_name,
                                'tag': tag_name,
                                'size': image_size,
                                'push_date': push_str,
                                'reason': status_reason
                            })
                        else:
                            # KEEP in ECR
                            repo_keep_count += 1
                            total_images_to_keep += 1
                            
                            write_output(output_file, f"|  -- KEEP ECR -- {tag_name:<35} {size_str:>10}  Pushed: {push_str}  ({status_reason})")
                            
                            kept_details.append({
                                'repo': repo_name,
                                'tag': tag_name,
                                'size': image_size,
                                'push_date': push_str,
                                'reason': status_reason
                            })
                    
                    # Repository summary
                    write_output(output_file, "|")
                    if repo_migrate_count > 0:
                        repositories_with_migrations += 1
                        write_output(output_file, f"|  Repository Summary: {repo_migrate_count} to migrate ({format_size(repo_migrate_size)}), {repo_keep_count} to keep in ECR")
                    else:
                        write_output(output_file, f"|  Repository Summary: All {repo_keep_count} images remain in ECR (recently used)")
                    
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
            write_output(output_file, "  Repositories Analyzed")
            write_output(output_file, "  " + "-" * 40)
            write_output(output_file, f"    Total scanned                : {repositories_processed}")
            write_output(output_file, f"    With images to migrate       : {repositories_with_migrations}")
            write_output(output_file, "")
            write_output(output_file, "  Images Analysis")
            write_output(output_file, "  " + "-" * 40)
            write_output(output_file, f"    Images to MIGRATE to S3      : {total_images_to_migrate}")
            write_output(output_file, f"    Images to KEEP in ECR        : {total_images_to_keep}")
            write_output(output_file, f"    Total images evaluated       : {total_images_to_migrate + total_images_to_keep}")
            write_output(output_file, "")
            write_output(output_file, "  Migration Size")
            write_output(output_file, "  " + "-" * 40)
            write_output(output_file, f"    Total data to migrate        : {format_size(total_size_bytes)}")
            write_output(output_file, "")
            
            if total_images_to_migrate > 0:
                write_output(output_file, "  Estimated Migration Time (at 1.33 MB/s)")
                write_output(output_file, "  " + "-" * 40)
                write_output(output_file, f"    {time_seconds:,.0f} seconds")
                write_output(output_file, f"    {time_minutes:,.1f} minutes")
                write_output(output_file, f"    {time_hours:,.2f} hours")
                if time_hours >= 24:
                    write_output(output_file, f"    {time_days:,.2f} days")
                write_output(output_file, "")
            else:
                write_output(output_file, "  [RESULT] No images qualify for migration!")
                write_output(output_file, "  All images in the date range have been pulled recently.")
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
                    write_output(output_file, f"  {idx:2d}. {img['repo']}/{img['tag']}")
                    write_output(output_file, f"      Size: {format_size(img['size'])}  |  {img['reason']}")
                    write_output(output_file, "")
            
            write_output(output_file, "")
            write_output(output_file, "=" * 80)
            write_output(output_file, "  Report saved to: " + output_filename)
            write_output(output_file, "=" * 80)
            print(f"\n*** Full report successfully saved to: {output_filename} ***")
            
        except Exception as e:
            error_msg = f"ERROR: Failed to access ECR: {e}"
            write_output(output_file, error_msg)

if __name__ == "__main__":
    calculate_migration_time()