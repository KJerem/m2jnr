"""PDF d'une facture (story S4.3), produit avec reportlab à partir des seules données figées.

- A4, polices standard Helvetica (encodage WinAnsi : « € », « œ », accents français) ;
- en-tête du garage, numéro, dates d'émission et d'échéance, client, véhicule, ordre de
  travail, lignes, totaux, mentions légales (SIRET, TVA intracommunautaire, capital, RCS,
  pénalités de retard, indemnité forfaitaire de 40 €, escompte) ;
- montants au format français (« 454,80 € ») ; les espaces insécables de l'interface sont
  remplacées par des espaces simples, que toutes les visionneuses affichent ;
- document « invariant » : ni date de production ni identifiant aléatoire, le même contenu
  donne les mêmes octets (modifier la fiche du client après l'émission ne change rien).
"""

from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.clock import date_locale
from app.models.devis import TypeLigne
from app.models.facture import Facture
from app.services.format import (
    formater_date,
    formater_euros,
    formater_km,
    formater_quantite,
)

MENTION_PENALITES = (
    "En cas de retard de paiement : pénalités au taux de trois fois le taux d'intérêt légal, "
    "et indemnité forfaitaire pour frais de recouvrement de 40 € (art. L441-10 et D441-5 du "
    "Code de commerce)."
)
MENTION_ESCOMPTE = "Pas d'escompte pour paiement anticipé."

ENCRE = colors.HexColor("#1d2125")
ENCRE_DOUCE = colors.HexColor("#5b636b")
FILET = colors.HexColor("#c9c4bb")
FOND = colors.HexColor("#efece6")

LARGEUR_UTILE = A4[0] - 36 * mm

STYLE = ParagraphStyle("texte", fontName="Helvetica", fontSize=9.5, leading=12.5, textColor=ENCRE)
STYLE_DOUX = ParagraphStyle("doux", parent=STYLE, textColor=ENCRE_DOUCE)
STYLE_GRAS = ParagraphStyle("gras", parent=STYLE, fontName="Helvetica-Bold")
STYLE_GARAGE = ParagraphStyle("garage", parent=STYLE_GRAS, fontSize=13, leading=16)
STYLE_TITRE = ParagraphStyle(
    "titre", parent=STYLE_GRAS, fontSize=18, leading=22, alignment=TA_RIGHT
)
STYLE_DROITE = ParagraphStyle("droite", parent=STYLE, alignment=TA_RIGHT)
STYLE_ETIQUETTE = ParagraphStyle(
    "etiquette", parent=STYLE_GRAS, fontSize=8, leading=10, textColor=ENCRE_DOUCE
)
STYLE_MENTION = ParagraphStyle("mention", parent=STYLE_DOUX, fontSize=8, leading=10.5)


def texte_pdf(valeur: object) -> str:
    """Texte prêt pour reportlab : espaces insécables remplacées, caractères XML échappés."""
    return escape(str(valeur).replace(" ", " ").replace(" ", " "))


def _p(valeur: object, style: ParagraphStyle = STYLE) -> Paragraph:
    return Paragraph(texte_pdf(valeur), style)


def _euros(centimes: int) -> str:
    return texte_pdf(formater_euros(centimes))


def _nom_client(client: dict[str, Any]) -> str:
    return " ".join(part for part in (client.get("prenom"), client.get("nom")) if part)


def _en_tete(facture: Facture, fuseau: str) -> Table:
    garage = facture.garage_fige
    gauche = [
        _p(garage["raison_sociale"], STYLE_GARAGE),
        _p(garage["adresse"], STYLE_DOUX),
        _p(f"Tél. {garage['telephone']} · {garage['email']}", STYLE_DOUX),
    ]
    droite = [
        _p(f"Facture {facture.numero}", STYLE_TITRE),
        _p(
            f"Date d'émission : {formater_date(date_locale(facture.emise_le, fuseau))}",
            STYLE_DROITE,
        ),
        _p(f"Date d'échéance : {formater_date(facture.echeance)}", STYLE_DROITE),
        _p(f"Ordre de travail : {facture.ordre.numero}", STYLE_DROITE),
    ]
    tableau = Table([[gauche, droite]], colWidths=[LARGEUR_UTILE * 0.55, LARGEUR_UTILE * 0.45])
    tableau.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (-1, 0), (-1, 0), 0),
            ]
        )
    )
    return tableau


def _parties(facture: Facture) -> Table:
    client = facture.client_fige
    vehicule = facture.vehicule_fige
    bloc_client = [_p("CLIENT", STYLE_ETIQUETTE), _p(_nom_client(client), STYLE_GRAS)]
    if client.get("telephone"):
        bloc_client.append(_p(f"Tél. {client['telephone']}"))
    if client.get("email"):
        bloc_client.append(_p(client["email"]))
    bloc_vehicule = [
        _p("VÉHICULE", STYLE_ETIQUETTE),
        _p(vehicule["immatriculation"], STYLE_GRAS),
        _p(f"{vehicule['marque']} {vehicule['modele']}"),
        _p(f"Kilométrage : {formater_km(int(vehicule['kilometrage']))}"),
    ]
    tableau = Table(
        [[bloc_client, bloc_vehicule]], colWidths=[LARGEUR_UTILE / 2 - 3 * mm] * 2, hAlign="LEFT"
    )
    tableau.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (0, 0), 0.6, FILET),
                ("BOX", (1, 0), (1, 0), 0.6, FILET),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return tableau


def _lignes(facture: Facture) -> Table:
    entete = [_p(t, STYLE_ETIQUETTE) for t in ("RÉFÉRENCE", "DÉSIGNATION")] + [
        _p(t, ParagraphStyle("e", parent=STYLE_ETIQUETTE, alignment=TA_RIGHT))
        for t in ("QTÉ", "PU HT", "TOTAL HT")
    ]
    donnees: list[list[Any]] = [entete]
    for ligne in facture.lignes:
        donnees.append(
            [
                _p(ligne.reference or "—"),
                _p(ligne.designation),
                _p(
                    formater_quantite(ligne.quantite, ligne.type == TypeLigne.MAIN_OEUVRE),
                    STYLE_DROITE,
                ),
                Paragraph(_euros(ligne.prix_unitaire_ht_centimes), STYLE_DROITE),
                Paragraph(
                    _euros(ligne.total_ht_centimes),
                    ParagraphStyle("t", parent=STYLE_GRAS, alignment=TA_RIGHT),
                ),
            ]
        )
    largeurs = [
        32 * mm,
        LARGEUR_UTILE - 32 * mm - 20 * mm - 26 * mm - 28 * mm,
        20 * mm,
        26 * mm,
        28 * mm,
    ]
    tableau = Table(donnees, colWidths=largeurs, repeatRows=1)
    tableau.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), FOND),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, FILET),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return tableau


def _totaux(facture: Facture) -> Table:
    main_oeuvre = sum(
        ligne.total_ht_centimes for ligne in facture.lignes if ligne.type == TypeLigne.MAIN_OEUVRE
    )
    taux = f"{facture.taux_tva_bp / 100:g}".replace(".", ",")
    style_total = ParagraphStyle("ttc", parent=STYLE_GRAS, fontSize=13, leading=16)
    style_total_droite = ParagraphStyle("ttcd", parent=style_total, alignment=TA_RIGHT)
    lignes = [
        ("Main-d'œuvre HT", main_oeuvre),
        ("Pièces HT", facture.total_ht_centimes - main_oeuvre),
        ("Total HT", facture.total_ht_centimes),
        (f"TVA {taux} %", facture.total_tva_centimes),
    ]
    donnees: list[list[Any]] = [
        [_p(libelle, STYLE_DOUX), Paragraph(_euros(montant), STYLE_DROITE)]
        for libelle, montant in lignes
    ]
    donnees.append(
        [
            _p("Total TTC", style_total),
            Paragraph(_euros(facture.total_ttc_centimes), style_total_droite),
        ]
    )
    tableau = Table(donnees, colWidths=[42 * mm, 34 * mm], hAlign="RIGHT")
    tableau.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, -1), (-1, -1), 0.8, ENCRE),
                ("TOPPADDING", (0, -1), (-1, -1), 6),
                ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
            ]
        )
    )
    return tableau


def _mentions(facture: Facture) -> list[Any]:
    garage = facture.garage_fige
    return [
        _p(f"Date d'échéance : {formater_date(facture.echeance)}", STYLE_GRAS),
        Spacer(1, 2 * mm),
        _p(MENTION_PENALITES, STYLE_MENTION),
        _p(MENTION_ESCOMPTE, STYLE_MENTION),
        Spacer(1, 3 * mm),
        _p(
            f"{garage['raison_sociale']} au capital de {garage['capital']} · {garage['rcs']} · "
            f"SIRET {garage['siret']} · TVA intracommunautaire {garage['tva_intracommunautaire']}",
            STYLE_MENTION,
        ),
        _p(f"{garage['adresse']} · Tél. {garage['telephone']} · {garage['email']}", STYLE_MENTION),
    ]


def generer_pdf(facture: Facture, fuseau: str = "Europe/Paris") -> bytes:
    """Octets du PDF de la facture (lignes et ordre chargés par l'appelant) ; la date
    d'émission est lue dans le fuseau du garage."""
    tampon = BytesIO()
    document = SimpleDocTemplate(
        tampon,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Facture {facture.numero}",
        author=facture.garage_fige["raison_sociale"],
        subject=f"Facture {facture.numero}",
        creator="Établi",
        invariant=1,
    )

    def pied(canvas: Canvas, doc: SimpleDocTemplate) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(ENCRE_DOUCE)
        canvas.drawRightString(
            A4[0] - 18 * mm, 9 * mm, f"Facture {facture.numero} · page {doc.page}"
        )
        canvas.restoreState()

    contenu: list[Any] = [
        _en_tete(facture, fuseau),
        Spacer(1, 8 * mm),
        _parties(facture),
        Spacer(1, 8 * mm),
        _lignes(facture),
        Spacer(1, 4 * mm),
        _totaux(facture),
        Spacer(1, 10 * mm),
        *_mentions(facture),
    ]
    document.build(contenu, onFirstPage=pied, onLaterPages=pied)
    return tampon.getvalue()
