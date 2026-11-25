# Open-Science Publishing Checklist

Follow these steps in order to timestamp your protocol, publish your repository, mint your Zenodo DOI, link your ORCID (`0009-0002-1777-0573`), and share your preprint.

---

## Step 1 — Push Repository to GitHub (`dhamodharankkp-oss`)
Switch your active `gh` account to `dhamodharankkp-oss`, create the public repository, and push:

```powershell
cd e:\AG\Blender\research\upper-limb-fdm-study
gh auth switch --user dhamodharankkp-oss
git add .
git commit -m "v0.1.0: Pediatric upper-limb TLM CAD, G-code ablation, and preprint draft"
gh repo create payir-upper-limb-tlm-fdm --public --source=. --remote=origin --push
```

---

## Step 2 — Timestamp Protocol on Open Science Framework (OSF)
1. Sign in to [https://osf.io/](https://osf.io/) (link your ORCID `0009-0002-1777-0573` in OSF Account Settings).
2. Click **Create new project**:
   - Title: `Payir Pediatric Upper-Limb Osteology TLM Kit & FDM Slicer Study`
   - Connect your GitHub repo `dhamodharankkp-oss/payir-upper-limb-tlm-fdm` under **Add-ons → GitHub**.
3. Go to **Registrations → New Registration → Open-Ended Registration** and paste `protocol/osf_preregistration.md`.
4. Submit to receive a permanent, timestamped **OSF Registration DOI** before running your `N = 3` caliper replicates (`K1-2026-R1..R6` in `data/raw/physical_print_log.csv`).

---

## Step 3 — Mint Citable Zenodo DOI & Sync ORCID
1. Log in to [https://zenodo.org/](https://zenodo.org/) using **"Log in with ORCID"** (`0009-0002-1777-0573`) or GitHub (`dhamodharankkp-oss`).
2. In Zenodo **GitHub settings** (`https://zenodo.org/account/settings/github/`), toggle ON **`dhamodharankkp-oss/payir-upper-limb-tlm-fdm`**.
3. Create a GitHub Release `v0.1.0`:
   ```powershell
   gh release create v0.1.0 --title "v0.1.0 — Pediatric Upper-Limb TLM CAD & Slicer Ablation" --notes "Initial open-science release (Payir Health Initiatives / Ideapattrai Makerspace)."
   ```
4. Zenodo will automatically archive the release and mint a **citable DOI** using `.zenodo.json`.
5. In Zenodo, enable **ORCID Auto-Update** (or add the Zenodo DOI to your ORCID Works list) so the dataset appears automatically on `https://orcid.org/0009-0002-1777-0573`.

---

## Step 4 — Publish Preprint (OSF Preprints or Zenodo)
1. Export `manuscript/preprint_draft.md` (with `manuscript/figures/*.png`) to PDF (e.g., via VS Code Markdown PDF or Chrome Print-to-PDF) after inserting your Zenodo DOI and OSF Registration URL in Section 5.
2. Upload to **OSF Preprints** (`https://osf.io/preprints/`) or **Zenodo** (`upload_type: publication / preprint`) to obtain a citable Preprint DOI.

---

## Step 5 — Target Open-Access Venues & University Collaborations
- **Primary Hardware Venues** (ideal for Option C):
  - *HardwareX* (Elsevier — Open Access, peer-reviewed open hardware)
  - *Journal of Open Hardware* (Ubiquity Press — low/waiverable APCs for community/non-profit initiatives)
- **Education / Additive Manufacturing Venues**:
  - *3D Printing in Medicine* / *Frontiers in Education (STEM Education)*
  - *ASEE Annual Conference* (Maker Education / Engineering Education)
- **University Co-Author Outreach**: Use your Zenodo DOI + ORCID record to approach local mechanical engineering or medical anatomy departments for formal tensile/compression testing or classroom RCT validation in `v2.0.0`.
