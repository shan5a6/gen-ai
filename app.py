import os
import re
import glob
import subprocess
import streamlit as st
import requests
import git
import yaml
from dotenv import load_dotenv
import shutil
import time

load_dotenv()

# --- Config ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")

BASE_DIR = os.getcwd()
TERRAFORM_DIR = os.path.join(BASE_DIR, "terraform")
PIPELINES_DIR = os.path.join(BASE_DIR, "pipelines", "github")

os.makedirs(TERRAFORM_DIR, exist_ok=True)
os.makedirs(PIPELINES_DIR, exist_ok=True)

# --- Groq call ---
def get_groq_response(prompt):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        raise Exception(f"Groq API Error: {response.text}")

# --- Universal extractor with .tfvars ---
def extract_blocks(raw_content):
    blocks = {}
    current_file = None
    buffer = []

    file_pattern = re.compile(
        r'^\**\s*([a-zA-Z0-9_\-/\.]+\.tf(vars)?|[a-zA-Z0-9_\-/\.]+\.ya?ml)\s*\**$',
        re.IGNORECASE
    )

    for line in raw_content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("```"):
            continue

        match = file_pattern.match(line)
        if match:
            filename = match.group(1)
            if current_file and buffer:
                blocks[current_file] = "\n".join(buffer).strip()
                buffer = []
            current_file = filename
            continue

        if current_file:
            buffer.append(line)

    if current_file and buffer:
        blocks[current_file] = "\n".join(buffer).strip()

    return blocks

# --- File ops ---
def clear_terraform_folder():
    for f in glob.glob(f"{TERRAFORM_DIR}/**/*.tf*", recursive=True):
        os.remove(f)

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content.strip())

# --- Terraform ops ---
def remove_ansi_colors(text):
    return re.sub(r'\x1b\[[0-9;]*m', '', text)

def run_terraform_command(command,tfvars=None):
    subprocess.run(["terraform", "init"], cwd=TERRAFORM_DIR, check=True, capture_output=True)
    args = ["terraform", command]
    if tfvars:
        args += ["-var-file", tfvars]
    if command in ["apply", "destroy"]:
        args.append("-auto-approve")
    result = subprocess.run(args, cwd=TERRAFORM_DIR, capture_output=True, text=True)
    return remove_ansi_colors(result.stdout + "\n" + result.stderr)

def validate_terraform():
    result = subprocess.run(["terraform", "validate"], cwd=TERRAFORM_DIR, capture_output=True, text=True)
    return remove_ansi_colors(result.stdout + "\n" + result.stderr)

def format_terraform():
    result = subprocess.run(["terraform", "fmt"], cwd=TERRAFORM_DIR, capture_output=True, text=True)
    return remove_ansi_colors(result.stdout + "\n" + result.stderr)


# --- Git ops ---
def is_git_repo():
    try:
        git.Repo(BASE_DIR).git_dir
        return True
    except git.exc.InvalidGitRepositoryError:
        return False
    
def clean_git_remote_url(url):
    # Replace fancy dashes or whitespace with simple hyphen and strip spaces
    url = url.strip()
    url = url.replace('—', '-')  # en-dash to hyphen
    url = url.replace('–', '-')  # em-dash to hyphen
    # You can add more replacements if needed
    return url

def git_init_and_remote(remote_url):
    repo = git.Repo.init(BASE_DIR)
    if remote_url:
        # Clean URL (replace fancy dashes etc if needed)
        remote_url = remote_url.strip()
        try:
            origin = None
            try:
                origin = repo.remote('origin')
            except ValueError:
                pass
            if origin:
                repo.delete_remote(origin)
            repo.create_remote('origin', remote_url)
        except Exception:
            pass
    return "✅ Git initialized!"

def git_status():
    repo = git.Repo(BASE_DIR)
    return repo.git.status()

def abort_ongoing_rebase(base_dir):
    rebase_merge = os.path.join(base_dir, ".git", "rebase-merge")
    rebase_apply = os.path.join(base_dir, ".git", "rebase-apply")

    for path in [rebase_merge, rebase_apply]:
        if os.path.exists(path):
            shutil.rmtree(path)

BASE_DIR = os.getcwd()

def run_cmd(cmd, cwd=None):
    result = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Command failed: {cmd}\nstdout: {result.stdout}\nstderr: {result.stderr}")
    return result.stdout.strip()

def git_commit_push(files, msg, branch, username, token):
    try:
        # Init repo if not exists
        if not os.path.exists(os.path.join(BASE_DIR, ".git")):
            repo = git.Repo.init(BASE_DIR)
            st.info("Initialized new Git repo.")
        else:
            repo = git.Repo(BASE_DIR)

        # Write .gitignore
        gitignore_path = os.path.join(BASE_DIR, ".gitignore")
        with open(gitignore_path, "w") as f:
            f.write("""
# ---- Virtual Environment ----
.venv/
.env
__pycache__/

# ---- Terraform ----
terraform/.terraform/
*.tfstate
*.tfstate.backup
crash.log

# ---- Python ----
__pycache__/
*.pyc

# ---- Secrets ----
.env

# ---- Editor ----
.vscode/
.idea/

# ---- OS files ----
.DS_Store
Thumbs.db
""".strip())
        repo.git.add(".gitignore")

        # Add files recursively or specific files
        if not files or "ALL" in files:
            repo.git.add(A=True)
        else:
            repo.git.add(files)

        # ✅ Only commit if dirty
        if repo.is_dirty(index=True, working_tree=True, untracked_files=True):
            repo.index.commit(msg)
            st.info("✅ New commit created.")
        else:
            st.info("✅ Nothing new to commit — will push anyway.")

        # Ensure origin remote exists
        try:
            origin = repo.remote('origin')
        except ValueError:
            remote_url = st.text_input("Enter remote URL for origin (required for push):")
            if not remote_url:
                raise Exception("Remote URL required to create 'origin'.")
            origin = repo.create_remote('origin', remote_url.strip())

        # Add credentials to remote URL
        remote_url = origin.url.strip().replace('—', '-').replace('–', '-')
        if remote_url.startswith("https://"):
            protocol_removed = remote_url[8:]
            if "@" in protocol_removed:
                protocol_removed = protocol_removed.split("@", 1)[-1]
            auth_url = f"https://{username}:{token}@{protocol_removed}"
            origin.set_url(auth_url)

        # Handle ongoing rebase (auto continue with commit --no-edit)
        rebase_merge_dir = os.path.join(BASE_DIR, ".git", "rebase-merge")
        rebase_apply_dir = os.path.join(BASE_DIR, ".git", "rebase-apply")

        if os.path.exists(rebase_merge_dir) or os.path.exists(rebase_apply_dir):
            st.warning("⚠️ Rebase in progress detected, attempting to continue rebase...")

            while os.path.exists(rebase_merge_dir) or os.path.exists(rebase_apply_dir):
                try:
                    # Stage all changes (resolved conflicts)
                    repo.git.add(A=True)
                    # Commit with no edit message (avoid editor)
                    run_cmd("git commit --no-edit", cwd=BASE_DIR)
                    # Continue rebase
                    run_cmd("git rebase --continue", cwd=BASE_DIR)
                    st.info("Git rebase --continue executed.")
                except Exception as e:
                    st.error(f"Failed to continue rebase automatically: {e}")
                    raise e

            st.success("✅ Rebase finished successfully.")
            return "Rebase completed, please retry your operation."

        # Checkout branch if exists or create
        remote_branches = [ref.name.split('/')[-1] for ref in origin.refs]
        if branch not in remote_branches:
            try:
                repo.git.push('--set-upstream', 'origin', branch)
            except Exception as e:
                st.error(f"Failed to set upstream: {e}")

        if branch in repo.heads:
            repo.git.checkout(branch)
        else:
            try:
                repo.git.checkout('-b', branch, f'origin/{branch}')
            except Exception:
                repo.git.checkout('-b', branch)

        # Pull with rebase to sync remote changes
        try:
            repo.git.pull('origin', branch, '--rebase')
        except Exception as e:
            st.warning(f"Pull with rebase failed: {e}. Trying without rebase.")
            repo.git.pull('origin', branch)

        # ✅ Always push!
        # --- Push changes ---
        push_result = origin.push(branch)

        for info in push_result:
            if info.flags & info.ERROR:
                if "refusing to allow a Personal Access Token to create or update workflow" in info.summary:
                    st.error(
                        "❌ Push rejected: Your GitHub token is missing the `workflow` scope.\n"
                        "➡️ Please recreate it with `repo` and `workflow` scopes."
                    )
                    return "❌ Push rejected due to missing `workflow` scope."
                else:
                    st.error(f"❌ Push failed: {info.summary}")
                    return f"❌ Push failed: {info.summary}"

        return f"✅ Commit, pull & push to {branch} done."


    except Exception as e:
        st.error(f"An error occurred: {e}")
        return f"❌ Error: {e}"


def create_pull_request(owner, repo_name, source_branch, target_branch, pr_title, pr_body,token):
    github_token = token
    if not github_token:
        raise Exception("❌ GITHUB_TOKEN not found — please set it in your .env or environment.")

    url = f"https://api.github.com/repos/{owner}/{repo_name}/pulls"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "title": pr_title,
        "head": source_branch,
        "base": target_branch,
        "body": pr_body
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 201:
        return response.json()["html_url"]
    else:
        raise Exception(f"❌ PR creation failed: {response.status_code} {response.text}")

# --- GitHub Actions helpers ---
import time

def list_workflows(owner, repo_name, token):
    url = f"https://api.github.com/repos/{owner}/{repo_name}/actions/workflows"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        workflows = resp.json()["workflows"]
        return [(wf["name"], wf["id"]) for wf in workflows]
    else:
        raise Exception(f"List workflows failed: {resp.text}")

def trigger_workflow(owner, repo_name, workflow_id, ref, token):
    url = f"https://api.github.com/repos/{owner}/{repo_name}/actions/workflows/{workflow_id}/dispatches"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "ref": ref  # branch name
    }
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code == 204:
        return True
    else:
        raise Exception(f"Trigger workflow failed: {resp.text}")

def get_workflow_runs(owner, repo_name, workflow_id, token):
    url = f"https://api.github.com/repos/{owner}/{repo_name}/actions/workflows/{workflow_id}/runs"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json()["workflow_runs"]
    else:
        raise Exception(f"Get workflow runs failed: {resp.text}")

def merge_pull_request(owner, repo_name, pr_number, token):
    url = f"https://api.github.com/repos/{owner}/{repo_name}/pulls/{pr_number}/merge"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    resp = requests.put(url, headers=headers)
    if resp.status_code == 200:
        return True
    else:
        raise Exception(f"Merge PR failed: {resp.text}")

def deploy_workflows_to_github(branch, username, token):
    workflows_dir = os.path.join(BASE_DIR, ".github", "workflows")
    pipelines_dir = os.path.join(BASE_DIR, "pipelines", "github")

    os.makedirs(workflows_dir, exist_ok=True)

    copied_files = []
    for file in glob.glob(f"{pipelines_dir}/*.yml"):
        filename = os.path.basename(file)
        dest = os.path.join(workflows_dir, filename)
        shutil.copyfile(file, dest)
        copied_files.append(dest)

    if not copied_files:
        return "❌ No workflow files found to deploy."

    # # Git push
    # repo = git.Repo(BASE_DIR)

    # repo.git.add(all=True)
    # repo.index.commit("Auto deploy workflows to .github/workflows")

    # origin = repo.remote('origin')

    # Inject credentials into remote URL
    # remote_url = origin.url.strip()
    # if remote_url.startswith("https://"):
    #     protocol_removed = remote_url[8:]
    #     if "@" in protocol_removed:
    #         protocol_removed = protocol_removed.split("@", 1)[-1]
    #     auth_url = f"https://{username}:{token}@{protocol_removed}"
    #     origin.set_url(auth_url)

    # origin.push(branch)

    #return f"✅ Workflows deployed & pushed: {copied_files}"
    return f"✅ Workflows deployed : {copied_files}"

# --- UI ---
st.set_page_config("Day 18 : GitOps Cockpit", layout="wide")
st.title("🚀 Day 18  - GitOps Cockpit (YAML & TFVARS)")

# Git
if not is_git_repo():
    st.warning("❌ Not a Git repo.")
    remote = st.text_input("Remote URL")
    if st.button("Git Init & Link"):
        st.success(git_init_and_remote(remote.strip() or None))
        st.experimental_rerun()
else:
    st.success(f"🗂 Git Status\n\n{git_status()}")

# Terraform
st.header("🔍 Terraform: Generate")
tf_prompt = st.text_area("Prompt for Terraform code", height=150)
if st.button("Generate Terraform"):
    with st.spinner("Calling LLM..."):
        out = get_groq_response(tf_prompt)
        clear_terraform_folder()
        blocks = extract_blocks(out)
        for f, code in blocks.items():
            write_file(os.path.join(TERRAFORM_DIR, f), code)
            st.expander(f).code(code)

# --- Add tfvars dropdown ---
tfvars_files = glob.glob(os.path.join(TERRAFORM_DIR, "*.tfvars"))
tfvars_files = [os.path.basename(f) for f in tfvars_files]
selected_tfvars = st.selectbox("Select .tfvars file", ["None"] + tfvars_files)

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("Terraform FMT"):
        st.text_area("Output", format_terraform(), height=300)
with col2:
    if st.button("Terraform Validate"):
        st.text_area("Output", validate_terraform(), height=300)
with col3:
    if st.button("Terraform Plan"):
        tfvars_path = selected_tfvars if selected_tfvars != "None" else None
        st.text_area("Output", run_terraform_command("plan", tfvars=tfvars_path), height=350)
if st.button("Terraform Apply"):
    st.text_area("Output", run_terraform_command("apply"), height=350)
if st.button("Terraform Destroy"):
    st.text_area("Output", run_terraform_command("destroy"), height=350)

# YAML
st.header("🔍 YAML: Search or Generate")

yaml_prompt = st.text_area("Prompt for YAML pipeline", height=150)

if st.button("Generate YAML"):
    with st.spinner("Calling LLM..."):
        out = get_groq_response(yaml_prompt)
        st.session_state['raw_groq_yaml'] = out
        blocks = extract_blocks(out)
        st.session_state['yaml_blocks'] = blocks
        st.success(f"✅ YAML/tfvars files generated: {', '.join(blocks.keys())}")

if 'raw_groq_yaml' in st.session_state:
    st.subheader("Raw Groq YAML Response (copy if needed)")
    st.code(st.session_state['raw_groq_yaml'], language='yaml')

if 'yaml_blocks' not in st.session_state:
    st.session_state.yaml_blocks = {}

if st.session_state.yaml_blocks:
    st.subheader("Edit & Save files (.yml/.tfvars) individually")

    for filename, content in st.session_state.yaml_blocks.items():
        if filename not in st.session_state:
            st.session_state[filename] = content

        edited_content = st.text_area(
            f"Edit '{filename}'",
            value=st.session_state[filename],
            height=300,
            key=f"edit_{filename}"
        )

        st.session_state[filename] = edited_content

        if st.button(f"💾 Save '{filename}'", key=f"save_{filename}"):
            if filename.endswith(".tfvars") or filename.endswith(".tf"):
                save_path = os.path.join(TERRAFORM_DIR, filename)
            else:
                save_path = os.path.join(PIPELINES_DIR, filename)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "w") as f:
                f.write(st.session_state[filename])
            st.success(f"✅ Saved: {save_path}")

# --- Git Commit ---
st.header("📌 Git Commit & Push")

# Get all files (terraform + pipelines)
all_files = [os.path.relpath(f, BASE_DIR) for f in glob.glob(f"{TERRAFORM_DIR}/**/*.tf", recursive=True)] + \
            [os.path.relpath(f, BASE_DIR) for f in glob.glob(f"{PIPELINES_DIR}/**/*.yml", recursive=True)]

# Add an "ALL" option
files_to_choose = ["ALL"] + all_files

files = st.multiselect("Files to commit (select 'ALL' to commit all files)", files_to_choose, default=["ALL"])

commit_msg = st.text_input("Commit Message", "Infra update")
branch = st.text_input("Branch", "main")
username = st.text_input("Git Username")
token = st.text_input("Git Token", type="password")

# --- PR UI ---
st.subheader("📌 Open Pull Request (Optional)")
owner = st.text_input("GitHub Repo Owner", "")
repo_name = st.text_input("GitHub Repo Name", "")
base_branch = st.text_input("Base Branch to merge into", "main")
pr_title = st.text_input("Pull Request Title", f"Auto PR from {branch}")
pr_body = st.text_area("Pull Request Body", "Automated PR for infra changes")

st.header("🚀 Deploy Workflows to GitHub")

if st.button("Deploy Workflows"):
    if not username or not token:
        st.error("Please provide Git username & token first.")
    else:
        result = deploy_workflows_to_github(branch, username, token)
        st.success(result)
        
st.header("🚀 Git Commit & Push")     
if st.button("Commit, Push"):
    try:
        result = git_commit_push(files, commit_msg, branch, username, token)
        st.success(result)
    except Exception as e:
        st.error(str(e))
        
st.header("🚀 Raise PR") 
if st.button("Create PR"):
    try:
        if owner and repo_name:
            pr_url = create_pull_request(owner, repo_name, branch, base_branch, pr_title, pr_body,token)
            st.success(f"✅ Pull Request Created: [View PR]({pr_url})")
    except Exception as e:
        st.error(str(e))


        
# --- CI/CD Orchestrator ---
st.header("🚦 CI/CD Orchestrator")

cicd_owner = st.text_input("GitHub Owner (CI/CD)", owner)
cicd_repo = st.text_input("GitHub Repo (CI/CD)", repo_name)
cicd_branch = st.text_input("Branch to deploy", branch)
cicd_token = token  # reuse same Git PAT

if st.button("🔍 List Workflows"):
    try:
        workflows = list_workflows(cicd_owner, cicd_repo, cicd_token)
        st.session_state["workflows"] = workflows
        st.success(f"Found: {', '.join([w[0] for w in workflows])}")
    except Exception as e:
        st.error(e)

if "workflows" in st.session_state:
    selected_wf = st.selectbox(
        "Select workflow to trigger",
        st.session_state["workflows"]
    )
    wf_name, wf_id = selected_wf

    if st.button("🚀 Trigger Workflow"):
        try:
            trigger_workflow(cicd_owner, cicd_repo, wf_id, cicd_branch, cicd_token)
            st.success(f"Triggered workflow: {wf_name} on branch {cicd_branch}")

            with st.spinner("⏳ Waiting for CI/CD run to complete..."):
                run_completed = False
                while not run_completed:
                    runs = get_workflow_runs(cicd_owner, cicd_repo, wf_id, cicd_token)
                    latest_run = runs[0] if runs else None
                    if latest_run:
                        status = latest_run["status"]
                        conclusion = latest_run.get("conclusion")
                        st.info(f"Status: {status} | Conclusion: {conclusion}")
                        if status == "completed":
                            run_completed = True
                            if conclusion == "success":
                                st.success("✅ CI/CD Passed!")
                                # Optional: Merge PR if you want
                                if st.checkbox("Auto-merge PR if CI passes"):
                                    pr_num = st.text_input("PR Number to merge")
                                    if st.button("🔀 Merge PR Now"):
                                        merge_pull_request(cicd_owner, cicd_repo, pr_num, cicd_token)
                                        st.success("PR merged! ✅")
                            else:
                                st.error("❌ CI/CD Failed.")
                            break
                        else:
                            time.sleep(5)
                    else:
                        st.warning("No runs found yet. Waiting...")
                        time.sleep(5)
        except Exception as e:
            st.error(e)


