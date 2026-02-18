# Derosa et al. 2025 — ICI Response Prediction (NSAT Cohort)

Demo dataset for PredomicsApp, derived from the study:

> **Derosa L, Routy B, et al.** *Gut microbiome composition as a predictive biomarker of immune checkpoint inhibitor (ICI) response.* 2025.

## Dataset Description

- **Domain:** Gut metagenomics (shotgun sequencing)
- **Features:** 2,834 Metagenomic Species Profiles (MSPs) — microbial species abundance
- **Endpoint:** Overall Survival at 12 months (OS12)
- **Classes:** Binary classification
  - `0` = OS12- (non-responder / overall survival < 12 months)
  - `1` = OS12+ (responder / overall survival >= 12 months)

## Files

| File | Rows | Columns | Description |
|------|------|---------|-------------|
| `Xtrain.tsv` | 2,834 | 229 | Discovery cohort feature matrix (MSPs x samples) |
| `Xtest.tsv` | 2,834 | 188 | Validation cohort feature matrix |
| `Ytrain.tsv` | 229 | 1 | Discovery labels (111 OS12-, 118 OS12+) |
| `Ytest.tsv` | 188 | 1 | Validation labels (81 OS12-, 107 OS12+) |

## Data Format

- Tab-separated values (TSV)
- `X` matrices: features in rows, samples in columns (transposed from typical ML convention)
- `Y` vectors: sample ID (BioSample accession) + binary class label
- Sample IDs: NCBI BioSample accessions (SAMN376XXXXX)
- Feature IDs: MSP identifiers (msp_XXXX)

## Usage with gpredomics

```yaml
# param.yaml excerpt
data:
  X: Xtrain.tsv
  y: Ytrain.tsv
  Xtest: Xtest.tsv
  ytest: Ytest.tsv
  classes:
    - "OS12-"
    - "OS12+"
    - "unknown"
  features_in_rows: true
```

## Reference

Derosa L, Routy B, et al. Gut microbiome composition as a predictive biomarker of immune checkpoint inhibitor (ICI) response. NSAT cohort — 229 discovery + 188 validation samples. 2025.
