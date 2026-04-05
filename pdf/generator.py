"""
OrientAgent - PDF Report Generator

Creates professional PDF reports using ReportLab.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Image,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY


# Custom colors
ORIENT_BLUE = colors.HexColor("#1E40AF")
ORIENT_GREEN = colors.HexColor("#059669")
ORIENT_ORANGE = colors.HexColor("#D97706")
LIGHT_GRAY = colors.HexColor("#F3F4F6")
DARK_GRAY = colors.HexColor("#374151")


def _get_styles():
    """Create custom paragraph styles."""
    styles = getSampleStyleSheet()
    
    styles.add(ParagraphStyle(
        name="Title_Custom",
        parent=styles["Title"],
        fontSize=28,
        textColor=ORIENT_BLUE,
        spaceAfter=20,
        alignment=TA_CENTER,
    ))
    
    styles.add(ParagraphStyle(
        name="Heading1_Custom",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=ORIENT_BLUE,
        spaceBefore=20,
        spaceAfter=12,
        borderColor=ORIENT_BLUE,
        borderWidth=1,
        borderPadding=5,
    ))
    
    styles.add(ParagraphStyle(
        name="Heading2_Custom",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=DARK_GRAY,
        spaceBefore=15,
        spaceAfter=8,
    ))
    
    styles.add(ParagraphStyle(
        name="Body_Custom",
        parent=styles["Normal"],
        fontSize=11,
        textColor=DARK_GRAY,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
        leading=16,
    ))
    
    styles.add(ParagraphStyle(
        name="Small",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.gray,
    ))
    
    styles.add(ParagraphStyle(
        name="Score_High",
        parent=styles["Normal"],
        fontSize=12,
        textColor=ORIENT_GREEN,
        alignment=TA_CENTER,
    ))
    
    styles.add(ParagraphStyle(
        name="Score_Medium",
        parent=styles["Normal"],
        fontSize=12,
        textColor=ORIENT_ORANGE,
        alignment=TA_CENTER,
    ))
    
    return styles


def _create_cover_page(result: dict, styles) -> list:
    """Create the cover page elements."""
    elements = []
    
    # Title
    elements.append(Spacer(1, 3*cm))
    elements.append(Paragraph("🎓 OrientAgent", styles["Title_Custom"]))
    elements.append(Paragraph("Rapport d'Orientation Personnalisé", styles["Heading2_Custom"]))
    elements.append(Spacer(1, 2*cm))
    
    # Student info
    nom = result.get("nom", "Étudiant")
    date = datetime.now().strftime("%d/%m/%Y")
    
    info_data = [
        ["Nom de l'étudiant:", nom],
        ["Série Baccalauréat:", result.get("serie_bac", "N/A")],
        ["Ville:", result.get("ville", "N/A")],
        ["Date du rapport:", date],
    ]
    
    info_table = Table(info_data, colWidths=[5*cm, 8*cm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 12),
        ("TEXTCOLOR", (0, 0), (0, -1), DARK_GRAY),
        ("TEXTCOLOR", (1, 0), (1, -1), ORIENT_BLUE),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    
    elements.append(info_table)
    elements.append(Spacer(1, 3*cm))
    
    # Footer text
    elements.append(Paragraph(
        "Ce rapport a été généré par OrientAgent, un système d'IA multi-agents "
        "conçu pour guider les lycéens marocains dans leur orientation post-bac. "
        "Les recommandations sont basées sur une analyse de votre profil académique "
        "et une recherche dans notre base de données de filières vérifiées.",
        styles["Body_Custom"]
    ))
    
    elements.append(PageBreak())
    
    return elements


def _create_profile_section(result: dict, styles) -> list:
    """Create the profile analysis section."""
    elements = []
    
    elements.append(Paragraph("1. Analyse de Votre Profil", styles["Heading1_Custom"]))
    
    # Domain scores table
    domain_scores = result.get("domain_scores", {})
    
    scores_data = [
        ["Domaine", "Score", "Niveau"],
    ]
    
    for domain, score in domain_scores.items():
        score_val = float(score)
        percentage = f"{score_val*100:.0f}%"
        
        if score_val >= 0.7:
            level = "Excellent ⭐"
        elif score_val >= 0.5:
            level = "Bon ✓"
        else:
            level = "À développer"
        
        domain_display = {
            "sciences": "Sciences",
            "tech": "Technologie",
            "lettres": "Lettres & Humanités",
            "economie": "Économie & Gestion",
        }.get(domain, domain.title())
        
        scores_data.append([domain_display, percentage, level])
    
    scores_table = Table(scores_data, colWidths=[6*cm, 3*cm, 4*cm])
    scores_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ORIENT_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
        ("BACKGROUND", (0, 1), (-1, -1), LIGHT_GRAY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    
    elements.append(scores_table)
    elements.append(Spacer(1, 1*cm))
    
    # Learning style
    learning_style = result.get("learning_style", "mixte")
    style_display = {
        "theorique": "Théorique - Tu préfères la compréhension conceptuelle et l'analyse",
        "pratique": "Pratique - Tu apprends mieux par l'expérimentation et les projets",
        "mixte": "Mixte - Tu combines théorie et pratique équitablement",
    }.get(learning_style, learning_style)
    
    elements.append(Paragraph("Style d'apprentissage:", styles["Heading2_Custom"]))
    elements.append(Paragraph(f"📚 {style_display}", styles["Body_Custom"]))
    
    elements.append(Spacer(1, 0.5*cm))
    
    return elements


def _create_recommendations_section(result: dict, styles) -> list:
    """Create the top 3 recommendations section."""
    elements = []
    
    elements.append(Paragraph("2. Top 3 Filières Recommandées", styles["Heading1_Custom"]))
    
    top_3 = result.get("top_3", [])
    
    if not top_3:
        elements.append(Paragraph(
            "Aucune recommandation disponible. Veuillez compléter votre profil.",
            styles["Body_Custom"]
        ))
        return elements
    
    for i, filiere in enumerate(top_3[:3], 1):
        # Filière header
        nom = filiere.get("filiere_nom", "N/A")
        score = filiere.get("score_final", 0)
        score_pct = f"{float(score)*100:.0f}%"
        
        elements.append(Paragraph(
            f"<b>{i}-  {nom}</b> — Score: {score_pct}",
            styles["Heading2_Custom"]
        ))
        
        # Details table
        details = [
            ["Type:", filiere.get("type", "N/A")],
            ["Ville:", filiere.get("ville", "N/A")],
        ]
        
        details_table = Table(details, colWidths=[3*cm, 10*cm])
        details_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.gray),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elements.append(details_table)
        
        # Justification
        justification = filiere.get("justification", "")
        if justification:
            elements.append(Paragraph(justification, styles["Body_Custom"]))
        
        # Action plan
        plan = filiere.get("plan_action_30j", [])
        if plan:
            elements.append(Paragraph("<b>Plan d'action (30 jours):</b>", styles["Body_Custom"]))
            for step in plan[:5]:
                elements.append(Paragraph(f"• {step}", styles["Body_Custom"]))
        
        elements.append(Spacer(1, 0.5*cm))
    
    return elements


def _create_interview_section(result: dict, styles) -> list:
    """Create the interview simulation results section."""
    elements = []
    
    interview_score = result.get("interview_score")
    interview_feedback = result.get("interview_feedback", {})
    
    if not interview_score and not interview_feedback:
        return elements
    
    elements.append(PageBreak())
    elements.append(Paragraph("3. Simulation d'Entretien", styles["Heading1_Custom"]))
    
    filiere_choisie = result.get("filiere_choisie", "")
    if filiere_choisie:
        elements.append(Paragraph(
            f"Filière testée: <b>{filiere_choisie}</b>",
            styles["Body_Custom"]
        ))
    
    # Score
    if interview_score is not None:
        elements.append(Spacer(1, 0.5*cm))
        
        score_color = ORIENT_GREEN if interview_score >= 70 else ORIENT_ORANGE
        score_style = "Score_High" if interview_score >= 70 else "Score_Medium"
        
        elements.append(Paragraph(
            f"<b>Score Global: {interview_score}/100</b>",
            styles[score_style]
        ))
    
    # Detailed scores
    details = interview_feedback.get("details", {})
    if details:
        elements.append(Spacer(1, 0.5*cm))
        
        scores_data = [
            ["Critère", "Score"],
            ["Clarté", f"{details.get('clarte_moyenne', 0)}/10"],
            ["Motivation", f"{details.get('motivation_moyenne', 0)}/10"],
            ["Connaissance", f"{details.get('connaissance_moyenne', 0)}/10"],
        ]
        
        scores_table = Table(scores_data, colWidths=[6*cm, 4*cm])
        scores_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), ORIENT_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(scores_table)
    
    # Strengths
    points_forts = interview_feedback.get("points_forts", [])
    if points_forts:
        elements.append(Spacer(1, 0.5*cm))
        elements.append(Paragraph("<b>✓ Points forts:</b>", styles["Body_Custom"]))
        for point in points_forts:
            elements.append(Paragraph(f"• {point}", styles["Body_Custom"]))
    
    # Areas for improvement
    axes = interview_feedback.get("axes_amelioration", [])
    if axes:
        elements.append(Spacer(1, 0.5*cm))
        elements.append(Paragraph("<b>→ Axes d'amélioration:</b>", styles["Body_Custom"]))
        for axe in axes:
            elements.append(Paragraph(f"• {axe}", styles["Body_Custom"]))
    
    return elements


def _create_sources_section(result: dict, styles) -> list:
    """Create the RAG sources transparency section."""
    elements = []
    
    filieres = result.get("filieres_retrieved", [])
    if not filieres:
        return elements
    
    elements.append(PageBreak())
    elements.append(Paragraph("4. Sources des Données", styles["Heading1_Custom"]))
    
    elements.append(Paragraph(
        "Les recommandations de ce rapport sont basées sur les filières suivantes, "
        "extraites de notre base de connaissances vérifiée:",
        styles["Body_Custom"]
    ))
    
    elements.append(Spacer(1, 0.5*cm))
    
    # List sources
    for f in filieres[:10]:
        nom = f.get("nom", f.get("filiere_nom", "N/A"))
        type_ = f.get("type", "N/A")
        elements.append(Paragraph(
            f"• {nom} ({type_})",
            styles["Small"]
        ))
    
    if len(filieres) > 10:
        elements.append(Paragraph(
            f"... et {len(filieres) - 10} autres filières analysées",
            styles["Small"]
        ))
    
    return elements


def _create_footer(styles) -> list:
    """Create the footer with disclaimer."""
    elements = []
    
    elements.append(Spacer(1, 2*cm))
    elements.append(Paragraph("—" * 40, styles["Small"]))
    elements.append(Paragraph(
        "Ce rapport a été généré par OrientAgent pour le Hackathon ENSET 2026. "
        "Les informations sont fournies à titre indicatif et ne remplacent pas "
        "les conseils d'un conseiller d'orientation professionnel. "
        "Vérifiez toujours les conditions d'admission auprès des établissements.",
        styles["Small"]
    ))
    elements.append(Paragraph(
        f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
        styles["Small"]
    ))
    
    return elements


def generate_report(result: dict) -> str:
    """
    Generate a PDF report from session results.
    
    Args:
        result: The StudentProfile state dict with all agent outputs
    
    Returns:
        Path to the generated PDF file
    """
    # Create output directory
    reports_dir = Path("./data/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename
    session_id = result.get("session_id", "unknown")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"orient_agent_{session_id}_{timestamp}.pdf"
    pdf_path = reports_dir / filename
    
    # Create document
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )
    
    # Get styles
    styles = _get_styles()
    
    # Build content
    elements = []
    
    # Cover page
    elements.extend(_create_cover_page(result, styles))
    
    # Profile section
    elements.extend(_create_profile_section(result, styles))
    
    # Recommendations section
    elements.extend(_create_recommendations_section(result, styles))
    
    # Interview section (if available)
    elements.extend(_create_interview_section(result, styles))
    
    # Sources section
    elements.extend(_create_sources_section(result, styles))
    
    # Footer
    elements.extend(_create_footer(styles))
    
    # Build PDF
    doc.build(elements)
    
    return str(pdf_path)
