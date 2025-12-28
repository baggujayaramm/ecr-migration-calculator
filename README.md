# ECR to S3 Migration Time Calculator

A production-ready Python tool that analyzes AWS Elastic Container Registry (ECR) repositories and calculates migration timelines for moving Docker images to S3 storage based on usage patterns.

---

## Overview

This tool helps DevOps teams and cloud architects plan container image migrations by:

- Scanning ECR repositories across AWS regions
- Identifying images based on last pull timestamps
- Calculating total migration size and estimated transfer time
- Generating comprehensive reports for capacity planning

**Key Use Case:** Optimize cloud storage costs by migrating infrequently-accessed container images from ECR to cheaper S3 storage while maintaining detailed audit trails.

---

## Features

- **Automated Image Discovery** - Scans single or all ECR repositories
- **Date-Range Filtering** - Identifies images based on configurable time windows
- **Size Calculations** - Accurate byte-to-GB conversions for capacity planning
- **Time Estimation** - Calculates migration duration based on network throughput (1.33 MB/s default)
- **Detailed Reporting** - Generates timestamped reports with top-10 largest images
- **Never-Pulled Detection** - Identifies images that have never been downloaded

---

## Architecture

```
┌─────────────┐
│   Python    │
│   Script    │
└──────┬──────┘
       │
       ├─── boto3 ────> AWS ECR API
       │                    │
       │                    ▼
       │              ┌──────────────┐
       │              │ Repositories │
       │              └──────────────┘
       │                    │
       │                    ▼
       │              ┌──────────────┐
       │              │    Images    │
       │              │  Metadata    │
       │              └──────────────┘
       │
       ▼
┌──────────────┐
│   Report     │
│  (txt file)  │
└──────────────┘
```

---

## Prerequisites

**System Requirements:**
- Python 3.8 or higher
- AWS account with ECR access
- IAM permissions: `ecr:DescribeRepositories`, `ecr:DescribeImages`

**Dependencies:**
```bash
pip install boto3 python-dotenv
```

---

## Installation

1. Clone the repository:
```bash
git clone https://github.com/baggujayaramm/ecr-migration-calculator.git
cd ecr-migration-calculator
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables (see Configuration section below)

---

## Configuration

Create a `.env` file in the project root:

```bash
# AWS Credentials
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key
AWS_REGION=us-east-1

# Migration Parameters
START_DATE=2024-01-01
END_DATE=2024-12-31

# Optional: Target specific repository (leave empty for all)
ECR_REPOSITORY_NAME=
```

### Configuration Parameters

| Parameter | Required | Description | Example |
|-----------|----------|-------------|---------|
| `AWS_ACCESS_KEY_ID` | Yes | AWS IAM access key | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | Yes | AWS IAM secret key | `wJalrXUt...` |
| `AWS_REGION` | Yes | AWS region identifier | `us-east-1` |
| `START_DATE` | Yes | Migration window start (YYYY-MM-DD) | `2024-01-01` |
| `END_DATE` | Yes | Migration window end (YYYY-MM-DD) | `2024-12-31` |
| `ECR_REPOSITORY_NAME` | No | Specific repository or empty for all | `my-app` or blank |

---

## Usage

Run the calculator:

```bash
python ecr_migration_calculator.py
```

**Output:**
- Console progress updates
- Timestamped report file: `ecr_migration_report_YYYYMMDD_HHMMSS.txt`

### Sample Output

```
+================================================================================+
|                                                                                |
|                   ECR TO S3 MIGRATION TIME CALCULATOR                          |
|                                                                                |
+================================================================================+

  Report Generated : 2024-12-29 14:30:45
  AWS Region       : us-east-1
  Target Scope     : All Repositories

+-- REPOSITORY: backend-api
|
|  >> MIGRATE >> api-v2.3.1            156.45 MB  Last pulled: 2024-06-15
|  >> MIGRATE >> api-v2.3.0            154.32 MB  Created: 2024-05-20
|
|  Repository Summary: 2 to migrate (310.77 MB)
```

---

## Migration Logic

Images are selected for migration when their **last pull timestamp** (or creation date if never pulled) falls within the configured date range.

**Decision Flow:**
```
Image → Has lastRecordedPullTime? 
         │
         ├─ Yes → Compare with START_DATE and END_DATE
         │         │
         │         └─ In Range? → MIGRATE
         │                      → Outside Range? → SKIP
         │
         └─ No → Use imagePushedAt (creation date)
                  │
                  └─ In Range? → MIGRATE (marked as "Created")
                               → Outside Range? → SKIP
```

---

## Report Structure

### 1. Repository Analysis
- Per-repository image breakdown
- Migration candidates with sizes and timestamps

### 2. Summary Statistics
- Total repositories scanned
- Total images analyzed
- Migration percentage
- Total data volume

### 3. Time Estimation
Based on 1.33 MB/s transfer rate:
- Seconds, minutes, hours, days

### 4. Top 10 Largest Migrations
Sorted by image size for prioritization

---

## Security Best Practices

⚠️ **Important:**

- Never commit `.env` files to version control
- Use IAM roles with least-privilege permissions
- Rotate AWS credentials regularly
- Consider using AWS Secrets Manager for production deployments

**Recommended `.gitignore`:**
```
.env
*.txt
__pycache__/
*.pyc
```

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Missing credentials | `.env` file not configured | Create `.env` with required keys |
| Repository not found | Invalid `ECR_REPOSITORY_NAME` | Verify repository name in AWS Console |
| Access denied | Insufficient IAM permissions | Add `ecr:Describe*` permissions |
| Invalid date format | Wrong date syntax | Use `YYYY-MM-DD` format |

---

## Performance Considerations

**Scan Time:**
- ~5-10 seconds per repository
- ~100 images/second processing rate

**Network:**
- Read-only operations (no modifications to ECR)
- Minimal API calls using pagination

**Scalability:**
- Tested with 500+ repositories
- Handles 10,000+ images efficiently

---

## Roadmap

- [ ] Multi-region support in single run
- [ ] Export reports to CSV/JSON formats
- [ ] Configurable transfer speed assumptions
- [ ] Integration with AWS Cost Explorer
- [ ] Dry-run mode with cost estimates

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

**Development Setup:**
```bash
git clone https://github.com/baggujayaramm/ecr-migration-calculator.git
cd ecr-migration-calculator
pip install -r requirements-dev.txt
```

---

## License

MIT License - see [LICENSE](LICENSE) file for details

---

## Technical Stack

- **Language:** Python 3.8+
- **AWS SDK:** boto3
- **Configuration:** python-dotenv
- **Output Format:** Plain text reports

---

## Contact & Support

**Author:** Baggu Jayaram  
**GitHub:** [@baggujayaramm](https://github.com/baggujayaramm)  
**LinkedIn:** [Your Profile](https://linkedin.com/in/yourprofile)

For issues and feature requests, please use the [GitHub Issues](https://github.com/baggujayaramm/ecr-migration-calculator/issues) page.

---

**⭐ If this tool helps your cloud cost optimization, consider giving it a star!**
