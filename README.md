# Pull Request: Image-Level Migration Evaluation

## Summary

Refactored ECR migration calculator to evaluate images individually based on their pull history, rather than making repository-level migration decisions.

## Changes Made

### Core Logic Update
- **Before**: Repository-level evaluation - if ANY image in a repo was pulled recently, ALL images stayed in ECR
- **After**: Image-level evaluation - each image is assessed independently based on its own pull history

### Migration Decision
Each image now evaluated individually:
```
IF image NOT pulled in last 365 days → MIGRATE to S3
IF image pulled within last 365 days → KEEP in ECR
```

This allows repositories to have:
- Some images in S3 (cold, unused)
- Some images in ECR (hot, actively used)

### Report Improvements
- Clear visual indicators: `>> MIGRATE >>` and `-- KEEP ECR --`
- Per-image reasoning with days since last pull
- Repository-level summaries showing split between migrate/keep
- Top 10 largest migrations section
- Windows-compatible ASCII formatting (no Unicode issues)

### Output Format
```
+-- REPOSITORY: my-app
|
|  >> MIGRATE >> v1.0    2.5 GB  (Last pulled 450 days ago)
|  -- KEEP ECR -- v2.0   2.6 GB  (Pulled 30 days ago)
|
|  Repository Summary: 1 to migrate, 1 to keep in ECR
```

## Impact

### Better Cost Optimization
- Only actively-used images stay in expensive ECR storage
- Unused images move to cheaper S3, even if repository has active images

### More Accurate Migration
- Previous logic could miss old images if repository had any recent activity
- New logic catches all unused images regardless of repository activity

### Real-World Example from Testing
- Repository `test-td-solutions`: 27 images evaluated
  - 24 images → S3 (176.22 GB saved from ECR)
  - 3 images → ECR (recently pulled)
- Previous logic would have kept all 27 in ECR

## Testing

Tested on 170 repositories:
- Successfully identified 70 images for migration (318.86 GB)
- Correctly retained 4 actively-used images in ECR
- Estimated migration time: 2.84 days at 1.33 MB/s

## Files Modified
- `migration_time.py` - Core evaluation logic refactored
- Report generation updated for image-level details

## Breaking Changes
None - script maintains same CLI interface and `.env` configuration