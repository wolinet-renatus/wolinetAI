import os
import re
import asyncio
import httpx
from pathlib import Path

WORKSPACE_ROOT = Path(os.getenv("WORKSPACE_ROOT", Path(__file__).resolve().parent.parent))
SKILLS_DIR = WORKSPACE_ROOT / ".agents/skills"
API_URL = "http://127.0.0.1:4000/claude-code/plugins"
AUTH_HEADER = {"Authorization": "Bearer sk-XvKFiwDoOtOe8i4lwbzb8Q", "Content-Type": "application/json"}

CATEGORY_MAP = {
    # Scientific Skills
    "bio": "Bioinformatics & Genomics",
    "rna": "Bioinformatics & Genomics",
    "gene": "Bioinformatics & Genomics",
    "variant": "Bioinformatics & Genomics",
    "genome": "Bioinformatics & Genomics",
    "dna": "Bioinformatics & Genomics",
    "crispr": "Bioinformatics & Genomics",
    "primer": "Bioinformatics & Genomics",
    "cell": "Bioinformatics & Genomics",
    "flow": "Bioinformatics & Genomics",
    "qiime": "Bioinformatics & Genomics",
    "phylogen": "Bioinformatics & Genomics",
    "rdkit": "Cheminformatics & Drug Discovery",
    "chem": "Cheminformatics & Drug Discovery",
    "dock": "Cheminformatics & Drug Discovery",
    "nmr": "Cheminformatics & Drug Discovery",
    "molecule": "Cheminformatics & Drug Discovery",
    "molfeat": "Cheminformatics & Drug Discovery",
    "medchem": "Cheminformatics & Drug Discovery",
    "protein": "Proteomics & Protein Engineering",
    "ms": "Proteomics & Protein Engineering",
    "mass-spec": "Proteomics & Protein Engineering",
    "esm": "Proteomics & Protein Engineering",
    "relion": "Proteomics & Protein Engineering",
    "clinical": "Clinical & Evidence Workflows",
    "trial": "Clinical & Evidence Workflows",
    "health": "Clinical & Evidence Workflows",
    "dicom": "Microscopy & Imaging",
    "microscop": "Microscopy & Imaging",
    "image": "Microscopy & Imaging",
    "pathology": "Microscopy & Imaging",
    "neuro": "Neuroscience & Electrophysiology",
    "bids": "Neuroscience & Electrophysiology",
    "nwb": "Neuroscience & Electrophysiology",
    "astronomy": "Physics & Astronomy",
    "astro": "Physics & Astronomy",
    "physics": "Physics & Astronomy",
    "quantum": "Physics & Astronomy",
    "qiskit": "Physics & Astronomy",
    "qutip": "Physics & Astronomy",
    "materials": "Materials Science & Simulation",
    "phase": "Materials Science & Simulation",
    "battery": "Engineering & Simulation",
    "cad": "Engineering & Simulation",
    "simulation": "Engineering & Simulation",
    "cantera": "Engineering & Simulation",
    "pybamm": "Engineering & Simulation",
    "lab": "Laboratory Automation",
    "opentrons": "Laboratory Automation",
    "paper": "Scientific Communication",
    "writing": "Scientific Communication",
    "literature": "Scientific Communication",
    "citation": "Scientific Communication",
    "poster": "Scientific Communication",
    "slides": "Scientific Communication",
    "scientific": "Scientific Research & Methods",
    "database": "Scientific & Data Access",
    "data": "Data Analysis & Statistics",
    "stats": "Data Analysis & Statistics",
    
    # Core Gateway & Engineering Skills
    "memory": "Memory & Recall",
    "ai-memory": "Memory & Recall",
    "test": "Testing & QA",
    "tdd": "Testing & QA",
    "review": "Code Review & Quality",
    "orch": "Agent Orchestration",
    "epic": "Project Management",
    "hookify": "Security & Guardrails",
    "security": "Security & Compliance",
    "hipaa": "Healthcare Compliance",
    "add-": "Gateway Administration",
    "update-": "Gateway Administration",
    "delete-": "Gateway Administration",
    "curvine": "Distributed Cache & Storage",
    "storage": "Distributed Cache & Storage",
    "python": "Language Patterns",
    "rust": "Language Patterns",
    "golang": "Language Patterns",
    "go-": "Language Patterns",
    "django": "Web Frameworks",
    "fastapi": "Web Frameworks",
    "spring": "Web Frameworks",
    "react": "Frontend & UI",
    "vue": "Frontend & UI",
    "flutter": "Mobile & Desktop",
    "kotlin": "Language Patterns",
    "cpp": "Language Patterns",
    "bigquery": "Data & Analytics",
    "gcp": "Cloud Infrastructure",
}

def detect_category(name: str) -> str:
    lower = name.lower()
    for prefix, cat in CATEGORY_MAP.items():
        if prefix in lower:
            return cat
    return "Engineering Skills"

def parse_skill(skill_dir: Path):
    name = skill_dir.name
    if not re.match(r"^[a-z0-9-]+$", name):
        return None
    
    skill_file = skill_dir / "SKILL.md"
    description = f"Autonomous skill for {name}"
    
    if skill_file.exists():
        content = skill_file.read_text(errors="ignore")
        fm_match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if fm_match:
            frontmatter = fm_match.group(1)
            desc_match = re.search(r'description:\s*["\']?(.*?)["\']?\s*$', frontmatter, re.MULTILINE)
            if desc_match:
                desc = desc_match.group(1).strip('"\'').strip()
                if desc:
                    description = desc
    
    # shorten description if too long
    if len(description) > 350:
        description = description[:347] + "..."
        
    category = detect_category(name)
    author_name = "Wolinet AI"
    repo = "affaan-m/ECC"
    domain = "Engineering"
    
    # Check if scientific skill
    if fm_match and "k-dense" in fm_match.group(1).lower():
        author_name = "K-Dense-AI"
        repo = "K-Dense-AI/scientific-agent-skills"
        domain = "Science"
    elif name.startswith(("add-", "update-", "delete-")):
        author_name = "BerriAI"
        repo = "BerriAI/litellm-skills"
        domain = "DevOps"
    elif "memory" in name:
        author_name = "akitaonrails"
        repo = "akitaonrails/ai-memory"
        domain = "Memory"
        
    return {
        "name": name,
        "source": {"source": "github", "repo": repo},
        "version": "1.0.0",
        "description": description,
        "author": {"name": author_name, "email": "support@wolinet.ai"},
        "category": category,
        "domain": domain,
        "keywords": [k for k in name.split("-") if len(k) > 2]
    }

async def register_skill(client: httpx.AsyncClient, skill_data: dict, sem: asyncio.Semaphore):
    async with sem:
        try:
            r = await client.post(API_URL, json=skill_data, headers=AUTH_HEADER, timeout=10.0)
            if r.status_code in (200, 201):
                return (skill_data["name"], "created")
            elif r.status_code == 409:
                return (skill_data["name"], "exists")
            else:
                return (skill_data["name"], f"error: {r.status_code} {r.text[:50]}")
        except Exception as e:
            return (skill_data["name"], f"exception: {str(e)[:50]}")

async def main():
    skills = []
    for p in sorted(SKILLS_DIR.iterdir()):
        if p.is_dir():
            s = parse_skill(p)
            if s:
                skills.append(s)
                
    print(f"Found {len(skills)} skills to register.")
    sem = asyncio.Semaphore(15)
    async with httpx.AsyncClient() as client:
        tasks = [register_skill(client, s, sem) for s in skills]
        results = await asyncio.gather(*tasks)
        
    created = sum(1 for _, res in results if res == "created")
    exists = sum(1 for _, res in results if res == "exists")
    errors = sum(1 for _, res in results if "error" in res or "exception" in res)
    print(f"Registration complete: {created} created, {exists} already existed, {errors} errors.")

if __name__ == "__main__":
    asyncio.run(main())
