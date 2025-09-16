#!/usr/bin/env python3
"""
Warframe Wiki PDF Generator
Converts YAML frontmatter + Markdown files to styled PDFs with interactive features
"""

import os
import sys
import yaml
import markdown
from datetime import datetime
from pathlib import Path
import argparse
import logging

# PDF generation dependencies
try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
except ImportError:
    print("WeasyPrint not installed. Install with: pip install weasyprint")
    sys.exit(1)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WarframePDFGenerator:
    def __init__(self, wiki_dir="../warframe-wiki", output_dir=None):
        self.wiki_dir = Path(wiki_dir)
        self.output_dir = Path(output_dir) if output_dir else self.wiki_dir / "pdfs"
        self.template_file = self.wiki_dir / "meta/templates/pdf_template.html"
        self.images_dir = self.wiki_dir / "images"

        # Ensure output directory exists
        self.output_dir.mkdir(exist_ok=True, parents=True)

        # Font configuration for better rendering
        self.font_config = FontConfiguration()

    def load_frontmatter(self, md_file):
        """Extract YAML frontmatter and markdown content from file"""
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()

            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    _, fm, body = parts
                    metadata = yaml.safe_load(fm)
                    return metadata or {}, body.strip()

            return {}, content
        except Exception as e:
            logger.error(f"Error loading {md_file}: {e}")
            return {}, ""

    def generate_stats_table(self, metadata):
        """Generate enhanced stats table with visual improvements"""
        if not any(key in metadata for key in ["fire_rate", "crit_chance", "status_chance", "disposition"]):
            return ""

        html = '<div class="stats-grid">'

        stats_mapping = {
            "fire_rate": ("Fire Rate", "rps"),
            "reload_time": ("Reload Time", "s"),
            "magazine_size": ("Magazine", "rounds"),
            "crit_chance": ("Critical Chance", "%"),
            "crit_multiplier": ("Critical Multiplier", "x"),
            "status_chance": ("Status Chance", "%"),
            "disposition": ("Riven Disposition", "●")
        }

        for key, (label, unit) in stats_mapping.items():
            if key in metadata:
                value = metadata[key]

                # Special formatting for percentages
                if unit == "%":
                    value = f"{float(value) * 100:.1f}" if isinstance(value, (int, float)) and value <= 1 else value
                elif key == "disposition":
                    value = "●" * int(value) + "○" * (5 - int(value))
                    unit = ""

                html += f'''
                <div class="stat-item">
                    <div class="stat-label">{label}</div>
                    <div class="stat-value">{value}{unit}</div>
                </div>
                '''

        html += '</div>'
        return html

    def generate_damage_breakdown(self, metadata):
        """Generate visual damage breakdown with bars"""
        if "damage_types" not in metadata:
            return ""

        damage_types = metadata["damage_types"]
        total_damage = sum(damage_types.values()) if isinstance(damage_types, dict) else 0

        if total_damage == 0:
            return ""

        html = '<h2>Damage Breakdown</h2><div class="damage-breakdown">'

        damage_colors = {
            "Impact": "impact-bar",
            "Puncture": "puncture-bar",
            "Slash": "slash-bar"
        }

        for damage_type, damage_value in damage_types.items():
            percentage = (damage_value / total_damage) * 100
            color_class = damage_colors.get(damage_type, "impact-bar")

            html += f'''
            <div class="damage-bar {color_class}" style="width: {percentage}%;">
                {damage_type}: {damage_value} ({percentage:.1f}%)
            </div>
            '''

        html += f'<p><strong>Total Damage: {total_damage}</strong></p></div>'
        return html

    def generate_builds_table(self, metadata):
        """Generate enhanced builds section with mod tags"""
        if "recommended_builds" not in metadata:
            return ""

        html = '<h2>Recommended Builds</h2>'

        for build in metadata["recommended_builds"]:
            build_name = build.get("name", "Unnamed Build")
            mods = build.get("mods", [])
            description = build.get("description", "")

            html += f'''
            <div class="build-card">
                <h3>{build_name}</h3>
                {f"<p>{description}</p>" if description else ""}
                <div class="mod-list">
            '''

            for mod in mods:
                html += f'<span class="mod-tag">{mod}</span>'

            html += '</div></div>'

        return html

    def generate_related_links(self, metadata):
        """Generate related items section with internal links"""
        if "related_items" not in metadata:
            return ""

        html = '<h2>Related Items</h2><ul>'

        for item in metadata["related_items"]:
            # Convert item name to potential file path
            safe_name = item.replace(" ", "_").lower()
            html += f'<li><a href="{safe_name}.pdf">{item}</a></li>'

        html += '</ul>'
        return html

    def render_html(self, metadata, md_content):
        """Render final HTML with all components"""
        try:
            with open(self.template_file, "r", encoding="utf-8") as f:
                template = f.read()
        except FileNotFoundError:
            logger.error(f"Template file not found: {self.template_file}")
            return ""

        # Convert markdown to HTML
        html_content = markdown.markdown(md_content, extensions=['tables', 'codehilite'])

        # Prepare template variables
        replacements = {
            "{{title}}": metadata.get("name", "Unknown Item"),
            "{{mastery_rank}}": str(metadata.get("mastery_rank", 0)),
            "{{release_date}}": metadata.get("release_date", "Unknown"),
            "{{last_updated}}": metadata.get("last_updated", "Unknown"),
            "{{generation_date}}": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "{{content}}": html_content,
            "{{stats_table}}": self.generate_stats_table(metadata),
            "{{damage_breakdown}}": self.generate_damage_breakdown(metadata),
            "{{builds_table}}": self.generate_builds_table(metadata),
            "{{related_links}}": self.generate_related_links(metadata),
        }

        # Handle image
        image_html = ""
        if "image" in metadata and metadata["image"]:
            image_path = self.images_dir / metadata["image"].lstrip("../images/")
            if image_path.exists():
                image_html = f'<img src="{image_path}" width="200" alt="{metadata.get("name", "")}">'

        replacements["{{image}}"] = image_html

        # Apply all replacements
        html_output = template
        for placeholder, value in replacements.items():
            html_output = html_output.replace(placeholder, str(value))

        return html_output

    def generate_pdf(self, md_file):
        """Generate PDF from markdown file"""
        try:
            metadata, md_content = self.load_frontmatter(md_file)

            if not metadata:
                logger.warning(f"No metadata found in {md_file}, skipping PDF generation")
                return False

            html = self.render_html(metadata, md_content)

            if not html:
                logger.error(f"Failed to render HTML for {md_file}")
                return False

            # Create safe filename
            safe_name = metadata.get('name', Path(md_file).stem).replace(" ", "_").replace("/", "_")
            output_file = self.output_dir / f"{safe_name}.pdf"

            # Generate PDF
            HTML(string=html, base_url=str(self.wiki_dir)).write_pdf(
                output_file,
                font_config=self.font_config
            )

            logger.info(f"Generated PDF: {output_file}")
            return True

        except Exception as e:
            logger.error(f"Error generating PDF for {md_file}: {e}")
            return False

    def walk_wiki_and_generate(self, category_filter=None):
        """Walk through wiki directory and generate PDFs"""
        generated_count = 0
        failed_count = 0

        for root, dirs, files in os.walk(self.wiki_dir):
            # Skip meta directories
            if "meta" in Path(root).parts or "pdfs" in Path(root).parts:
                continue

            # Apply category filter if specified
            if category_filter and category_filter not in str(root):
                continue

            for file in files:
                if file.endswith(".md"):
                    md_file = Path(root) / file

                    if self.generate_pdf(md_file):
                        generated_count += 1
                    else:
                        failed_count += 1

        logger.info(f"PDF Generation Complete: {generated_count} successful, {failed_count} failed")

def main():
    parser = argparse.ArgumentParser(description="Generate PDFs from Warframe wiki markdown files")
    parser.add_argument("--wiki-dir", default="../warframe-wiki", help="Wiki directory path")
    parser.add_argument("--output-dir", help="Output directory for PDFs")
    parser.add_argument("--category", help="Filter by category (weapons, warframes, etc.)")
    parser.add_argument("--file", help="Generate PDF for specific file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    generator = WarframePDFGenerator(args.wiki_dir, args.output_dir)

    if args.file:
        # Generate single file
        generator.generate_pdf(args.file)
    else:
        # Generate all files
        generator.walk_wiki_and_generate(args.category)

if __name__ == "__main__":
    main()