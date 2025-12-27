# ECR Migration Calculator

A Python tool for calculating migration time and cost estimation for AWS ECR repositories based on usage patterns and date ranges.

## Overview

This tool helps DevOps teams plan container image migrations by analyzing ECR repositories, identifying unused images, and estimating transfer times. It uses repository-level pull history to determine which images should be migrated.

## Key Features

- Analyzes ECR repositories based on last pull timestamp
- Filters images by date range for targeted migration planning
- Calculates migration time estimates based on network speed
- Generates detailed reports with skipped repository information
- Supports single repository or full ECR account scanning

## Prerequisites

- Python 3.7+
- AWS account with ECR access
- IAM permissions: `ecr:DescribeRepositories`, `ecr:DescribeImages`

## Installation

```bash
git clone https://github.com/yourusername/ecr-migration-calculator.git
cd ecr-migration-calculator
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root:

```env
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
ECR_REPOSITORY_NAME=
START_DATE=2023-12-01
END_DATE=2023-12-31
```

**Security Note:** The `.env` file contains sensitive AWS credentials and must never be committed to version control. The included `.gitignore` file prevents this by excluding `.env` from git tracking, protecting against unauthorized access and potential security breaches.

## Usage

**Scan all repositories:**
```bash
python migration_time.py
```

**Scan specific repository:**
```env
ECR_REPOSITORY_NAME=my-backend-api
```

## How It Works

1. Connects to AWS ECR using provided credentials
2. Scans repositories for images within the specified date range
3. Checks repository pull history (last 365 days)
4. Migrates repositories not pulled in the last year
5. Calculates total size and estimated migration time
6. Generates detailed report with both migrated and skipped repositories

## Output

The tool provides:
- Real-time console output
- Detailed text report saved as `ecr_migration_report_YYYYMMDD_HHMMSS.txt`

**Report includes:**
- Repository scan summary
- Images to migrate with sizes
- Skipped repositories with pull dates
- Total migration size and time estimates

## Example Output

```
======================================================================
COMPLETE MIGRATION SUMMARY
======================================================================
Total repositories scanned: 15
Repositories to migrate: 8
Repositories skipped (pulled recently): 7
Total images to migrate: 45
Total migration size: 12500.50 MB (12.21 GB)

Migration speed: 1.33 MB/s

Estimated migration time:
  - 156.64 minutes
  - 2.61 hours
```

## Configuration Options

**Adjust migration speed** (in `migration_time.py`):
```python
speed_mb_per_sec = 1.33  # Change to match your network speed
```

**Modify time threshold**:
```python
one_year_ago = datetime.now() - timedelta(days=365)  # Adjust days as needed
```

## Dependencies

```
boto3>=1.26.0
python-dotenv>=1.0.0
```

## Security Best Practices

- Never commit `.env` files to version control
- Use IAM roles instead of access keys when possible
- Apply least privilege principle for IAM permissions
- Rotate AWS credentials regularly
- Review `.gitignore` to ensure sensitive files are excluded

## Troubleshooting

**Authentication Error:**
- Verify AWS credentials in `.env` file
- Ensure IAM permissions are correctly configured

**Repository Not Found:**
- Check repository name spelling
- Verify repository exists in the specified region

## License

MIT License

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

---

**⚠️ Security Warning:** This tool requires AWS credentials. Follow security best practices and never share your `.env` file.
