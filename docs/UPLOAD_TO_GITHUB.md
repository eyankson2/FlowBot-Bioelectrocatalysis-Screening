# Publish this repository on GitHub — step-by-step (Windows)

This guide uses Git from PowerShell. **Do not upload the ZIP as the only GitHub file**; extract it and commit the **contents** so visitors can browse `README.md`, source code and documentation. This guide does not require the researcher to share passwords with anyone.

## Before publishing: clearance and authorship review

1. Read [`ATTRIBUTION_AND_LICENSE.md`](ATTRIBUTION_AND_LICENSE.md). Check university/sponsor permission, upstream license obligations, any unpublished recipe or device details, and the README's attribution wording.
2. Review the `CITATION.cff` author list and add co-developers as appropriate. This example uses the author name Emmanuel Yankson based on the supplied project context; check institutional software authorship and affiliation details. Do **not** claim sole ownership unless verified.
3. Inspect all files for passwords, tokens, collaborator details, personal file paths, sensitive laboratory configuration or unpublished experimental results. This package contains source/templates/example only; repeat this review whenever new files are added.
4. For manuscript reproducibility, decide whether to publish under your personal GitHub account or your lab/organization account, and agree on the owner with your coauthors. If hosted by an organization, use the proper repository collaborator permissions and the Git **commit author** identity for development credit.

## A. Create the empty GitHub repository

1. Sign in at [https://github.com](https://github.com).
2. Click the **+** menu near the upper-right corner, then **New repository** (or open `https://github.com/new`).
3. Choose the repository **Owner** (personal account or organization).
4. Enter **`FlowBot-Bioelectrocatalysis-Screening`** as the **Repository name**.
5. Suggested description: `Python automation platform for three-cell Bio-Logic bioelectrocatalysis screening, solution mixing, and nitrogen-solenoid control.`
6. Choose **Private** if clearance/licensing review is outstanding; select **Public** only after receiving approval. Repositories can be made public later in Settings, subject to organization rules.
7. **Do not select** *Add a README*, *Add .gitignore*, or *Choose a license*; all are included in the local folder.
8. Click **Create repository** and copy the HTTPS address. It will be similar to `https://github.com/YOUR_ACCOUNT/FlowBot-Bioelectrocatalysis-Screening.git`.

## B. Upload the local folder using Git

1. Install [Git for Windows](https://git-scm.com/download/win) if needed. Open **PowerShell** and check `git --version`.
2. Extract `FlowBot-Bioelectrocatalysis-Screening_GitHub_Ready.zip` to a short local path (e.g. `C:\GitHub\`). Use **Extract All**, not a ZIP viewer.
3. Open PowerShell inside the extracted folder containing `README.md` and `app.py`. In File Explorer, click the folder address bar, type `powershell`, then press Enter. Alternatively:

   ```powershell
   cd "C:\GitHub\FlowBot-Bioelectrocatalysis-Screening"
   ```

4. Set your Git commit identity *if this PC does not already have one*. Use your GitHub-connected email or GitHub no-reply email:

   ```powershell
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ```

5. Initialize, review, add and commit the files:

   ```powershell
   git init -b main
   git status
   git add .
   git status
   git commit -m "Initial release of FlowBot bioelectrocatalysis screening software"
   ```

   **Check `git status` before committing**; it should not show private experimental files or large `.mpr` datasets. `git add .` is appropriate only after review.

6. Point your local project to the empty online repository (replace `YOUR_ACCOUNT` with your actual GitHub user or lab organization):

   ```powershell
   git remote add origin https://github.com/YOUR_ACCOUNT/FlowBot-Bioelectrocatalysis-Screening.git
   git remote -v
   git push -u origin main
   ```

7. If asked to sign in, complete GitHub's browser/device authentication or a supported Git credential-manager flow. **Do not paste a GitHub account password into a remote Git prompt**. Organizations may require SSO authorization.
8. Refresh the repository page. You should see the source files and rendered `README.md`; under **About**, set an informative description/topics such as `electrochemistry`, `bioelectrocatalysis`, `automation`, `flowbot`, `biologic`, and `laboratory-automation`.

> **If `remote origin already exists`**: run `git remote -v` to inspect the configured URL, then change it only if needed with `git remote set-url origin https://github.com/YOUR_ACCOUNT/FlowBot-Bioelectrocatalysis-Screening.git`.
>
> **If push is rejected due to a non-empty remote**: check whether you created a README or license on GitHub. For a brand-new repository, the simplest safe remedy is to create a truly empty repository and push to it; do **not** use `git push --force` without understanding the impact.

## C. Publish later updates

Any time you change one or more `.py`/documentation files, open PowerShell in the repository folder and run:

```powershell
git status
git add .
git commit -m "Describe the software update"
git push
```

Before each `git add .`, make sure no new experimental data, credentials or restricted documents were copied into the tracked folders. `git status` and `git diff` help you review your changes.

## D. Reference a stable release in a manuscript

1. After scientific and license review, mark a specific revision for the manuscript. On GitHub go to the repository sidebar **Releases** > **Create a new release**; create a tag such as `v1.0.0`, describe the version, and publish. For a prerelease, mark it accordingly.
2. Because `CITATION.cff` is present, GitHub can show a **Cite this repository** link on the repository page. Review the generated author/title information.
3. Consider connecting the repository to [Zenodo](https://zenodo.org/) and archiving the published GitHub release. After Zenodo returns a **DOI**, update the repository README/CITATION metadata appropriately and use that DOI in the manuscript. No DOI exists until an archive has actually been deposited.
4. Include both the *specific release/commit* and a link to the project, and acknowledge the eLab, Easy-Biologic and biologic-com foundations separately. The manuscript text template is in [`MANUSCRIPT_CITATION.md`](MANUSCRIPT_CITATION.md).
5. Keep scientific data and experimental records under a separate approved data-deposition policy; GitHub software publication by itself does not establish data availability.

**Official reference:** [GitHub Docs — Adding locally hosted code to GitHub](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github).
