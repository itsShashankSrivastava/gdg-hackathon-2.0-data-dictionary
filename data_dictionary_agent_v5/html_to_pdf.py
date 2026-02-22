"""
HTML Presentation to PDF Converter
Converts presentation.html to a PDF file
"""

import asyncio
import sys
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Installing playwright...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    from playwright.async_api import async_playwright


async def convert_html_to_pdf(html_path: str, pdf_path: str):
    """Convert HTML presentation to PDF using Playwright"""
    
    html_file = Path(html_path).resolve()
    if not html_file.exists():
        print(f"Error: HTML file not found: {html_file}")
        return False
    
    print(f"Converting: {html_file}")
    print(f"Output: {pdf_path}")
    
    async with async_playwright() as p:
        # Launch headless browser
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Navigate to the HTML file
        await page.goto(f"file:///{html_file}")
        
        # Wait for content to load
        await page.wait_for_load_state("networkidle")
        
        # Get total number of slides
        total_slides = await page.evaluate("""
            () => document.querySelectorAll('.slide').length
        """)
        print(f"Found {total_slides} slides")
        
        # Generate PDF with all slides visible
        # First, make all slides visible for PDF export
        await page.evaluate("""
            () => {
                // Show all slides for PDF
                const slides = document.querySelectorAll('.slide');
                slides.forEach((slide, index) => {
                    slide.style.display = 'flex';
                    slide.style.position = 'relative';
                    slide.style.pageBreakAfter = 'always';
                    slide.style.height = '100vh';
                    slide.style.minHeight = '100vh';
                });
                
                // Hide navigation elements
                const nav = document.querySelector('.nav-hint');
                if (nav) nav.style.display = 'none';
                
                const progress = document.querySelector('.progress-bar');
                if (progress) progress.style.display = 'none';
            }
        """)
        
        # Generate PDF
        await page.pdf(
            path=pdf_path,
            format="A4",
            landscape=True,
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"}
        )
        
        await browser.close()
        
    print(f"PDF created successfully: {pdf_path}")
    return True


def main():
    # Default paths
    script_dir = Path(__file__).parent
    html_path = script_dir / "presentation.html"
    pdf_path = script_dir / "presentation.pdf"
    
    # Allow custom paths via command line
    if len(sys.argv) >= 2:
        html_path = Path(sys.argv[1])
    if len(sys.argv) >= 3:
        pdf_path = Path(sys.argv[2])
    
    # Run conversion
    asyncio.run(convert_html_to_pdf(str(html_path), str(pdf_path)))


if __name__ == "__main__":
    main()
