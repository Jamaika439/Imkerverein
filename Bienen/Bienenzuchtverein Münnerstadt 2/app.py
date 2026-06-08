import os
import uuid
import urllib.request
import urllib.parse
from datetime import datetime, timezone, date
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename




app = Flask(__name__)
app.secret_key = 'imker_geheimnis_2026'

# ==============================================================================
# 1. KONFIGURATION & ORDNERSYSTEM
# ==============================================================================
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bienenstock.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Maximal 16MB

db = SQLAlchemy(app)
ADMIN_PW = "Imker2026!"

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# ==============================================================================
# 2. DATENBANK-MODELLE (SQLAlchemy)
# ==============================================================================

class Content(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seite = db.Column(db.String(50), unique=True)
    titel = db.Column(db.String(200))  
    text = db.Column(db.Text)

class HomeContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titel_oben = db.Column(db.String(200), default='Herzlich Willkommen')
    text_oben = db.Column(db.Text)
    img1 = db.Column(db.String(100))
    img2 = db.Column(db.String(100))
    img3 = db.Column(db.String(100))
    text_unten = db.Column(db.Text)

class GalleryBlock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    beschreibung = db.Column(db.String(300))
    bilder = db.relationship('ImageGallery', backref='block', lazy=True, cascade="all, delete-orphan")

class ImageGallery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100))
    caption = db.Column(db.String(200))
    block_id = db.Column(db.Integer, db.ForeignKey('gallery_block.id'), nullable=False)

class BieneImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100))
    x_pos = db.Column(db.Integer, default=50)  
    y_pos = db.Column(db.Integer, default=50)  

class KontaktAnfrage(db.Model):
    __tablename__ = 'kontakt_anfragen'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    nachricht = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class Vorstand(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name_rolle = db.Column(db.String(200), nullable=False)  
    beschreibung = db.Column(db.Text)                       
    image_filename = db.Column(db.String(100))              
    reihenfolge = db.Column(db.Integer, default=0)          

class VorstandImage(db.Model):
    __tablename__ = 'vorstand_images'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    caption = db.Column(db.String(200), nullable=False)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titel = db.Column(db.String(200), nullable=False)
    datum = db.Column(db.Date, nullable=False)
    uhrzeit = db.Column(db.String(50))  # z.B. "14:00 - 18:00"
    beschreibung = db.Column(db.Text)
    bild = db.Column(db.String(200))     # Dateiname des hochgeladenen Bildes
    ist_cafe = db.Column(db.Boolean, default=False) # Unterscheidung Café-Termin vs. normales Event


# ==============================================================================
# 3. DATENBANK INITIALISIERUNG & HTML-GERÜST-INJEKTOR
# ==============================================================================

# Hier definieren wir deine exakten HTML-Strukturen als Startkapital für die DB
GERUEST_IMPRESSUM = """<h3>Angaben gemäß § 5 TMG</h3>
<p>
    <strong>Name des Vereins / Anbieters</strong><br>
    Imkerverein [Name deines Vereins] e.V.<br>
    [Straße und Hausnummer des Vereinsheims oder des 1. Vorsitzenden]<br>
    [PLZ und Ort]
</p>

<p>
    <strong>Vertreten durch den Vorstand:</strong><br>
    [Vorname Nachname, 1. Vorsitzende/r]<br>
    [Vorname Nachname, 2. Vorsitzende/r]
</p>

<h3>Kontakt</h3>
<p>
    Telefon: [Deine Telefonnummer oder die des Vereins]<br>
    E-Mail: [Deine Vereins-E-Mail-Adresse]
</p>

<h3>Registereintrag (falls vorhanden)</h3>
<p>
    Eintragung im Vereinsregister.<br>
    Registergericht: Amtsgericht [Name des Ortes, z.B. Frankfurt am Main]<br>
    Registernummer: VR [Deine Registernummer]
</p>

<h3>Redaktionell verantwortlich</h3>
<p>
    [Vorname Nachname desjenigen, der die Inhalte pflegt – z.B. du oder der Vorstand]<br>
    [Straße und Hausnummer]<br>
    [PLZ und Ort]
</p>

<h3>EU-Streitschlichtung</h3>
<p>
    Die Europäische Kommission stellt eine Plattform zur Online-Streitbeilegung (OS) bereit: 
    <a href="https://ec.europa.eu/consumers/odr/" target="_blank" rel="noopener noreferrer" style="color: var(--honey-dark);">https://ec.europa.eu/consumers/odr/</a>.<br>
    Unsere E-Mail-Adresse finden Sie oben im Impressum.
</p>

<p style="font-size: 0.9rem; color: var(--bee-text); opacity: 0.7; margin-top: 50px;">
    
</p>"""

GERUEST_DATENSCHUTZ = """<h3>1. Datenschutz auf einen Blick</h3>
<p>
    Die folgenden Hinweise geben einen einfachen Überblick darüber, was mit Ihren personenbezogenen Daten passiert, wenn Sie diese Website besuchen. Personenbezogene Daten sind alle Daten, mit denen Sie persönlich identifiziert werden können.
</p>

<h3>2. Allgemeine Hinweise und Pflichtinformationen</h3>
<p>
    <strong>Verantwortliche Stelle:</strong><br>
    Imkerverein [Name deines Vereins] e.V.<br>
    [Straße und Hausnummer]<br>
    [PLZ und Ort]<br>
    E-Mail: [Deine Vereins-E-Mail-Adresse]
</p>
<p>
    Die verantwortliche Stelle entscheidet allein oder gemeinsam mit anderen über die Zwecke und Mittel der Verarbeitung von personenbezogenen Daten (z.&nbsp;B. Namen, Kontaktdaten o. Ä.).
</p>
<p>
    <strong>Widerruf Ihrer Einwilligung zur Datenverarbeitung:</strong><br>
    Viele Datenverarbeitungsvorgänge sind nur mit Ihrer ausdrücklichen Einwilligung möglich. Sie können eine bereits erteilte Einwilligung jederzeit widerrufen. Dazu reicht eine formlose Mitteilung per E-Mail an uns. Die Rechtmäßigkeit der bis zum Widerruf erfolgten Datenverarbeitung bleibt vom Widerruf unberührt.
</p>
<p>
    <strong>Beschwerderecht bei der zuständigen Aufsichtsbehörde:</strong><br>
    Im Falle von Verstößen gegen die DSGVO steht den Betroffenen ein Beschwerderecht bei einer Aufsichtsbehörde, insbesondere in dem Mitgliedstaat ihres Aufenthaltsortes, ihres Arbeitsplatzes oder des Orts des mutmäßlichen Verstoßes zu.
</p>

<h3>3. Datenerfassung auf dieser Website</h3>
<p>
    <strong>Server-Log-Files:</strong><br>
    Der Provider der Seiten erhebt und speichert automatisch Informationen in sogenannten Server-Log-Files, die Ihr Browser automatisch an uns übermittelt. Dies sind: Browsertyp und Browserversion, verwendetes Betriebssystem, Referrer URL, Hostname des zugreifenden Rechners, Uhrzeit der Serveranfrage und die IP-Adresse. Eine Zusammenführung dieser Daten mit anderen Datenquellen wird nicht vorgenommen. Grundlage für die Datenverarbeitung ist Art. 6 Abs. 1 lit. f DSGVO.
</p>

<p>
    <strong>Registrierung und Benutzer-Login (Admin-Bereich):</strong><br>
    Wenn Sie sich auf unserer Website registrieren oder im Admin-Bereich einloggen, verarbeiten wir die von Ihnen eingegebenen Daten (z.&nbsp;B. E-Mail-Adresse, Passwort-Hashes) sowie sitzungsrelevante Daten (Sitzungs-Cookies), um Ihnen den Zugang zu den zugriffsgeschützten Funktionen zu ermöglichen. Die Verarbeitung erfolgt auf Grundlage von Art. 6 Abs. 1 lit. b DSGVO zur Vertragserfüllung oder Durchführung vorvertraglicher Maßnahmen. Die Daten verbleiben in unserer Datenbank, bis Sie Ihr Konto löschen oder der Zweck für die Datenspeicherung entfällt.
</p>

<p>
    <strong>Kontaktformular / Eingaben in der Admin-Konsole:</strong><br>
    Wenn Sie uns per Kontaktformular Anfragen zukommen lassen oder als Administrator Inhalte (wie Texte oder Galeriebilder) einpflegen, werden Ihre Angaben inklusive der von Ihnen dort angegebenen Kontaktdaten zwecks Bearbeitung der Anfrage und für den Fall von Anschlussfragen bei uns in der Datenbank gespeichert. Diese Daten geben wir nicht ohne Ihre Einwilligung weiter.
</p>

<h3>4. Plugins und Tools</h3>
<p>
    <strong>Google Web Fonts:</strong><br>
    Diese Seite nutzt zur einheitlichen Darstellung von Schriftarten sogenannte Web Fonts, die von Google bereitgestellt werden. Beim Aufruf einer Seite lädt Ihr Browser die benötigten Web Fonts in ihren Browsercache, um Texte und Schriftarten korrekt anzuzeigen.
</p>
<p>
    Zu diesem Zweck muss der von Ihnen verwendete Browser Verbindung zu den Servern von Google aufnehmen. Hierdurch erlangt Google Kenntnis darüber, dass über Ihre IP-Adresse unsere Website aufgerufen wurde. Die Nutzung von Google Web Fonts erfolgt im Interesse einer einheitlichen und ansprechenden Darstellung unserer Online-Angebote. Dies stellt ein berechtigtes Interesse im Sinne von Art. 6 Abs. 1 lit. f DSGVO dar.
</p>
<p>
    Wenn Ihr Browser Web Fonts nicht unterstützt, wird eine Standardschrift Ihres Computers genutzt. Weitere Informationen zu Google Web Fonts finden Sie unter <a href="https://developers.google.com/fonts/faq" target="_blank" rel="noopener noreferrer" style="color: var(--honey-dark);">https://developers.google.com/fonts/faq</a>.
</p>

<p style="font-size: 0.9rem; color: var(--bee-text); opacity: 0.7; margin-top: 50px;">
</p>"""

with app.app_context():
    db.create_all()
    
    standard_seiten = {
        'start': ('Start', ''),
        'verein': ('Entstehung', 'Infos zur Vereinsentstehung...'),
        'verein_bildung': ('Bildungsangebot', 'Infos zu unseren Kursen...'),
        'caffee': ('Bienen-Caffee', 'Genießen Sie unseren Honig.'),
        'caffee_unten': ('nein|14:00|18:00', ''),
        'termine': ('Termine', 'de.german%23holiday%40group.v.calendar.google.com'),
        'biene': ('Die Biene', 'Hier entstehen spannende Infos über Bienen...'),
        'impressum': ('Impressum', GERUEST_IMPRESSUM),      # Direkt mit Struktur vorbelegen!
        'datenschutz': ('Datenschutz', GERUEST_DATENSCHUTZ)   # Direkt mit Struktur vorbelegen!
    }

    for seite_id, (titel, text) in standard_seiten.items():
        existing_item = Content.query.filter_by(seite=seite_id).first()
        if not existing_item:
            db.session.add(Content(seite=seite_id, titel=titel, text=text))
        else:
            # Falls der Eintrag existiert, aber leer oder veraltet ist, überschreiben wir ihn einmalig mit deinem Gerüst
            if seite_id in ['impressum', 'datenschutz'] and (not existing_item.text or "Hier stehen unsere" in existing_item.text or "Hier steht unsere" in existing_item.text):
                existing_item.text = text
                existing_item.titel = titel
    
    db.session.commit()
        
    if not HomeContent.query.first():
        db.session.add(HomeContent(text_oben='Willkommen beim Imkerverein.', text_unten='Wir freuen uns auf Sie!'))
        db.session.commit()


# ==============================================================================
# 4. ÖFFENTLICHE ROUTEN (Frontend)
# ==============================================================================

@app.route('/verein')
def verein():
    return render_template('verein.html', 
                           c=Content.query.filter_by(seite='verein').first(), 
                           verein_bildung=Content.query.filter_by(seite='verein_bildung').first(),
                           vorstandschaft=VorstandImage.query.all())

@app.route('/')
def index():
    return render_template('index.html', home=HomeContent.query.first())

@app.route('/caffee')
def caffee():
    inhalt_oben = Content.query.filter_by(seite='caffee').first()
    inhalt_unten = Content.query.filter_by(seite='caffee_unten').first()
    termine_content = Content.query.filter_by(seite='termine').first()
    return render_template('caffee.html', c=inhalt_oben, c_unten=inhalt_unten, termine=termine_content)

# 🟢 BESUCHER-ANSICHT: Termine-Seite




@app.route('/termine')
def termine():
    ical_url = "https://outlook.office365.com/owa/calendar/ee07e7e6ef5c4c4abdde3f030cbbbd42@Imkervereinmuennerstadt.onmicrosoft.com/861858045ed24bb08f655f42093cbd755840352322019263249/calendar.ics"
    
    events_liste = []
    heute = datetime.now().date()
    
    try:
        req = urllib.request.Request(ical_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as response:
            ical_text = response.read().decode('utf-8')
            
        ical_text = ical_text.replace("\r\n ", "").replace("\r\n\t", "").replace("\n ", "").replace("\n\t", "")
        raw_events = ical_text.split("BEGIN:VEVENT")
        
        for raw_item in raw_events[1:]:
            event_obj = {
                'uid': '',       # Für den Einzel-Export benötigt
                'titel': 'Unbenannte Veranstaltung',
                'datum': None,
                'uhrzeit': '',
                'beschreibung': '',
                'location': '',  # Speicherort für die Adresse
                'maps_url': '',  # Fertiger Google Maps Link
                'bild': None,
                'typ_text': 'Verein', 
                'bg_farbe': '#B37427', 
                'text_farbe': '#FFFFFF',
                'emoji': '🐝'
            }
            
            start_zeit = ""
            end_zeit = ""
            ist_geoeffnet_termin = False
            
            for zeile in raw_item.splitlines():
                if zeile.startswith("END:VCALENDAR"):
                    continue
                
                # UID auslesen
                if zeile.startswith("UID:"):
                    event_obj['uid'] = zeile.replace("UID:", "").strip()
                    
                elif zeile.startswith("SUMMARY:"):
                    titel_text = zeile.replace("SUMMARY:", "").strip()
                    event_obj['titel'] = titel_text
                    titel_lower = titel_text.lower()
                    
                    if "geöffnet" in titel_lower or "geoffnet" in titel_lower:
                        ist_geoeffnet_termin = True
                        break
                    
                    if "caf" in titel_lower:
                        event_obj['typ_text'] = 'Café'
                        event_obj['bg_farbe'] = '#2C1E12'
                        event_obj['text_farbe'] = '#FFB300'
                        event_obj['emoji'] = '☕'
                    elif "stammtisch" in titel_lower:
                        event_obj['typ_text'] = 'Stammtisch'
                        event_obj['bg_farbe'] = '#4a69bd'
                        event_obj['text_farbe'] = '#ffffff'
                        event_obj['emoji'] = '🍻'
                    elif "schulung" in titel_lower or "lehrgang" in titel_lower or "vortrag" in titel_lower:
                        event_obj['typ_text'] = 'Schulung'
                        event_obj['bg_farbe'] = '#20bf6b'
                        event_obj['text_farbe'] = '#ffffff'
                        event_obj['emoji'] = '🎓'
                    elif "kesselfleisch" in titel_lower or "mahlzeit" in titel_lower:
                        event_obj['typ_text'] = 'Mahlzeit'
                        event_obj['bg_farbe'] = '#c0392b' 
                        event_obj['text_farbe'] = '#ffffff'
                        event_obj['emoji'] = '🥩'
                    elif "fest" in titel_lower or "feier" in titel_lower:
                        event_obj['typ_text'] = 'Fest'
                        event_obj['bg_farbe'] = '#eb3b5a'
                        event_obj['text_farbe'] = '#ffffff'
                        event_obj['emoji'] = '🥳'

                elif zeile.startswith("DESCRIPTION:"):
                    event_obj['beschreibung'] = zeile.replace("DESCRIPTION:", "").replace("\\n", "\n").strip()
                
                # 🔥 NEU: Ort auslesen und Maps-URL generieren
                elif zeile.startswith("LOCATION:"):
                    ort = zeile.replace("LOCATION:", "").strip()
                    if ort:
                        event_obj['location'] = ort
                        # Macht die Adresse URL-sicher (z.B. Leerzeichen zu %20)
                        event_obj['maps_url'] = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(ort)}"
                    
                elif zeile.startswith("DTSTART"):
                    raw_date = zeile.split(":")[-1].strip()
                    try:
                        pure_date_str = raw_date[:8]
                        event_obj['datum'] = datetime.strptime(pure_date_str, "%Y%m%d").date()
                        if "T" in raw_date and len(raw_date) >= 13:
                            start_zeit = f"{raw_date[9:11]}:{raw_date[11:13]}"
                    except:
                        pass

                elif zeile.startswith("DTEND"):
                    raw_end = zeile.split(":")[-1].strip()
                    try:
                        if "T" in raw_end and len(raw_end) >= 13:
                            end_zeit = f"{raw_end[9:11]}:{raw_end[11:13]}"
                    except:
                        pass

            if ist_geoeffnet_termin:
                continue

            if start_zeit and end_zeit:
                event_obj['uhrzeit'] = f"{start_zeit} - {end_zeit} Uhr"
            elif start_zeit:
                event_obj['uhrzeit'] = f"Ab {start_zeit} Uhr"

            if event_obj['datum']:
                events_liste.append(event_obj)
                
    except Exception as e:
        print("Kritischer Fehler beim iCal-Import:", e)

    kommende = [e for e in events_liste if e['datum'] >= heute]
    kommende.sort(key=lambda x: x['datum'])
    
    vergangene = [e for e in events_liste if e['datum'] < heute]
    vergangene.sort(key=lambda x: x['datum'], reverse=True)

    return render_template('termine.html', kommende=kommende, vergangene=vergangene)

# 🎛️ ADMIN-ACTION: Neues Event erstellen
@app.route('/admin/event/add', methods=['POST'])
def add_event():
    if not session.get('admin'):
        return redirect('/login')
        
    titel = request.form.get('titel')
    datum_str = request.form.get('datum')
    uhrzeit = request.form.get('uhrzeit')
    beschreibung = request.form.get('beschreibung')
    ist_cafe = 'ist_cafe' in request.form # Checkbox
    
    datum = datetime.strptime(datum_str, "%Y-%m-%d").date()
    
    # Bild-Upload verarbeiten
    file = request.files.get('event_bild')
    filename = None
    if file and file.filename != '':
        filename = secure_filename(f"event_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
        file.save(os.path.join(UPLOAD_FOLDER, filename))
        
    neues_event = Event(
        titel=titel, datum=datum, uhrzeit=uhrzeit, 
        beschreibung=beschreibung, bild=filename, ist_cafe=ist_cafe
    )
    db.session.add(neues_event)
    db.session.commit()
    
    return redirect('/admin') # oder wo dein Dashboard liegt

# 🗑️ ADMIN-ACTION: Event löschen
@app.route('/admin/event/delete/<int:id>', methods=['POST'])
def delete_event(id):
    if not session.get('admin'):
        return redirect('/login')
    event = Event.query.get_or_create(id)
    if event:
        # Bild falls vorhanden aus dem Dateisystem löschen
        if event.bild:
            try:
                os.remove(os.path.join(UPLOAD_FOLDER, event.bild))
            except:
                pass
        db.session.delete(event)
        db.session.commit()
    return redirect('/termine')

@app.route('/galerie')
def galerie():
    return render_template('galerie.html', bloecke=GalleryBlock.query.all())

@app.route('/die_biene')
def die_biene():
    # 1. Text mit dem korrekten Bezeichner 'biene' laden
    biene_data = Content.query.filter_by(seite='biene').first()
    
    # 2. Die dazugehörigen Bilder aus deiner Bild-Tabelle laden
    # (Passe 'BieneImage' an den echten Namen deines Bild-Modells an!)
    images = BieneImage.query.all() 
    
    # 3. Variablen exakt so benennen, wie dein Dashboard es erwartet (biene und biene_images)
    return render_template('die_biene.html', biene=biene_data, biene_images=images)

@app.route('/impressum')
def impressum():
    db_content = Content.query.filter_by(seite='impressum').first()
    return render_template('impressum.html', impressum=db_content)

@app.route('/datenschutz')
def datenschutz():
    db_content = Content.query.filter_by(seite='datenschutz').first()
    return render_template('datenschutz.html', datenschutz=db_content)

@app.route('/kontakt')
def kontakt(): 
    return render_template('kontakt.html')

@app.route('/kontakt/senden', methods=['POST'])
def kontakt_senden():
    name = request.form.get('name')
    email = request.form.get('email')
    nachricht = request.form.get('message')
    if not name or not email or not nachricht or not request.form.get('dsgvo'):
        flash("Bitte alle Felder ausfüllen und Datenschutz akzeptieren.", "error")
        return redirect(url_for('kontakt'))
    try:
        db.session.add(KontaktAnfrage(name=name, email=email, nachricht=nachricht))
        db.session.commit()
        return render_template('kontakt.html', erfolg=True)
    except Exception as e:
        db.session.rollback()
        return redirect(url_for('kontakt'))


# ==============================================================================
# 5. AUTHENTIFIZIERUNG & ADMIN CORE
# ==============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('pw') == ADMIN_PW:
            session['admin'] = True
            return redirect(url_for('admin'))
        else: 
            error = "Falsches Passwort!"
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('index'))

@app.route('/admin')
def admin():
    if not session.get('admin'): return redirect(url_for('login'))
    return render_template('admin.html', 
                           start=Content.query.filter_by(seite='start').first(),
                           verein=Content.query.filter_by(seite='verein').first(),
                           verein_vorstand=Content.query.filter_by(seite='verein_vorstand').first(), # 🌟 NEU
                           verein_bildung=Content.query.filter_by(seite='verein_bildung').first(),
                           verein_kontakt=Content.query.filter_by(seite='verein_kontakt').first(),   # 🌟 NEU
                           caffee=Content.query.filter_by(seite='caffee').first(),
                           caffee_unten=Content.query.filter_by(seite='caffee_unten').first(),
                           termine=Content.query.filter_by(seite='termine').first(),
                           biene=Content.query.filter_by(seite='biene').first(),
                           impressum=Content.query.filter_by(seite='impressum').first(),
                           datenschutz=Content.query.filter_by(seite='datenschutz').first(),
                           home=HomeContent.query.first(),
                           bloecke=GalleryBlock.query.all(),
                           biene_images=BieneImage.query.all(),
                           vorstandschaft=VorstandImage.query.all())


# ==============================================================================
# 6. MANAGEMENT ROUTEN (Inhalte & Vorstände)
# ==============================================================================

@app.route('/admin/save/<seite>', methods=['POST'])
def save_content(seite):
    if not session.get('admin'): return "Unbefugt", 403
    
    neuer_titel = request.form.get('titel')
    neuer_text = request.form.get('text')
    
    item = Content.query.filter_by(seite=seite).first()
    
    # 🌟 FIX: Falls der Eintrag noch nicht existiert, neu erzeugen!
    if not item:
        item = Content(seite=seite)
        db.session.add(item)
    
    # Jetzt können wir die Werte sicher für bestehende oder neue Einträge setzen
    item.titel = neuer_titel  
    item.text = neuer_text
    
    db.session.commit()
        
    return redirect(url_for('admin'))

@app.route('/add_vorstand', methods=['POST'])
def add_vorstand():
    if not session.get('admin'): return "Unbefugt", 403
    
    caption = request.form.get('caption')
    file = request.files.get('foto')
    
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(upload_path)
        
        try:
            neues_mitglied = VorstandImage(filename=filename, caption=caption)
            db.session.add(neues_mitglied)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Fehler beim Speichern des Vorstands: {e}")
        
    return redirect(url_for('admin'))

@app.route('/delete_vorstand/<int:id>', methods=['POST'])
def delete_vorstand(id):
    if not session.get('admin'): return "Unbefugt", 403
    
    member = VorstandImage.query.get(id)
    if member:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], member.filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError as e:
                print(f"Datei konnte nicht gelöscht werden: {e}")
        
        try:
            db.session.delete(member)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Fehler beim Löschen aus der DB: {e}")
            
    return redirect(url_for('admin'))



@app.context_processor
def inject_sidebar_status():
    from datetime import datetime
    import urllib.request

   # 1. Nächsten Café-Termin aus der Datenbank laden
    caffee_status = Content.query.filter_by(seite='caffee_unten').first()
    
    # Hier holen wir den String. Falls er leer ist oder noch das alte "nein|..." enthält,
    # setzen wir direkt ein sauberes Standard-Format ein:
    status_string = caffee_status.titel if (caffee_status and caffee_status.titel) else '2026-06-11|13:30|17:30'
    if "ja" in status_string or "nein" in status_string:
        status_string = '2026-06-11|13:30|17:30' # Altes Format rigoros überschreiben
    
    naechster_termin_text = "Termin folgt"
    cafe_ist_jetzt_offen = False
    uhrzeit_text = "13:30 - 17:30 Uhr" # Schöner Standard-Wert

    try:
        teile = status_string.split('|')
        if len(teile) >= 3:
            datum_str, von_str, bis_str = teile[0], teile[1], teile[2]
            uhrzeit_text = f"{von_str} - {bis_str} Uhr"
            
            # Datum und Zeiten parsen
            termin_datum = datetime.strptime(datum_str, "%Y-%m-%d").date()
            jetzt = datetime.now()
            heute = jetzt.date()
            
            # Wochentage auf Deutsch übersetzen
            wochentage = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
            wochentag_de = wochentage[termin_datum.weekday()]
            
            # Formatiere das Datum (z.B. Do, 11.06.2026)
            deutsches_datum = termin_datum.strftime("%d.%m.%Y")
            naechster_termin_text = f"{wochentag_de}, {deutsches_datum}"

            # LIVE-PRÜFUNG
            if heute == termin_datum:
                von_zeit = datetime.strptime(von_str, "%H:%M").time()
                bis_zeit = datetime.strptime(bis_str, "%H:%M").time()
                jetzt_zeit = jetzt.time()
                
                if von_zeit <= jetzt_zeit <= bis_zeit:
                    cafe_ist_jetzt_offen = True
        else:
            # Falls beim Splitten was schiefgeht (z.B. zu wenige Spalten):
            naechster_termin_text = "Do, 11.06.2026"
    except Exception as e:
        print("Fehler beim Berechnen des Café-Status:", e)
        naechster_termin_text = "Do, 11.06.2026" # Dein gewünschter Standard, falls die DB streikt

    # 2. Kalender-Prüfung für allgemeine Vereinstermine (unverändert)
    morgen_status_text = "Keine Termine."
    termine_content = Content.query.filter_by(seite='termine').first()
    if termine_content and termine_content.text:
        from datetime import timedelta
        try:
            morgen_str = (datetime.now().date() + timedelta(days=1)).strftime("%Y%m%d")
            ical_url = "https://outlook.office365.com/owa/calendar/ee07e7e6ef5c4c4abdde3f030cbbbd42@Imkervereinmuennerstadt.onmicrosoft.com/861858045ed24bb08f655f42093cbd755840352322019263249/calendar.ics"
            req = urllib.request.Request(ical_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as response:
                if morgen_str in response.read().decode('utf-8'):
                    morgen_status_text = "🚨 Termin geplant!"
        except Exception:
            morgen_status_text = "Nicht erreichbar"

    return dict(
        home_caffee_status=status_string,
        cafe_offen_live=cafe_ist_jetzt_offen,      # True oder False (Prüft Datum + Uhrzeit)
        naechster_cafe_termin=naechster_termin_text,# Gibt z.B. "Do, 11.06.2026" aus
        cafe_uhrzeit=uhrzeit_text,                  # Gibt z.B. "13:30 - 17:30 Uhr" aus
        morgen_status=morgen_status_text
    )

    
@app.route('/admin/postfach')
def admin_postfach():
    if not session.get('admin'): return redirect(url_for('login'))
    return render_template('admin_postfach.html', nachrichten=KontaktAnfrage.query.order_by(KontaktAnfrage.created_at.desc()).all())

@app.route('/admin/update_home', methods=['POST'])
def update_home():
    if not session.get('admin'): return redirect(url_for('login'))
    home = HomeContent.query.first()
    home.titel_oben, home.text_oben, home.text_unten = request.form.get('titel_oben'), request.form.get('text_oben'), request.form.get('text_unten')
    for i in range(1, 4):
        f = request.files.get(f'img{i}')
        if f and f.filename != '':
            fname = secure_filename(f.filename)
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
            setattr(home, f'img{i}', fname)
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/gallery/create_album', methods=['POST'])
def create_album():
    if not session.get('admin'): return redirect(url_for('login'))
    name, desc = request.form.get('album_name'), request.form.get('album_beschreibung')
    if name and not GalleryBlock.query.filter_by(name=name).first():
        db.session.add(GalleryBlock(name=name, beschreibung=desc))
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/gallery/upload_to_album', methods=['POST'])
def upload_to_album():
    if not session.get('admin'): return redirect(url_for('login'))
    block_id = request.form.get('block_id')
    files, captions = request.files.getlist('foto'), request.form.getlist('caption')
    if block_id and files:
        for i, f in enumerate(files):
            if f and f.filename != '':
                fname = secure_filename(f.filename)
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                db.session.add(ImageGallery(filename=fname, caption=captions[i] if i < len(captions) else '', block_id=int(block_id)))
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/gallery/delete_album/<int:id>', methods=['POST'])
def delete_album(id):
    if not session.get('admin'): return redirect(url_for('login'))
    block = GalleryBlock.query.get(id)
    if block:
        for b in block.bilder:
            try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], b.filename))
            except OSError: pass
        db.session.delete(block)
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/biene/upload', methods=['POST'])
def upload_biene_image():
    if not session.get('admin'): return redirect(url_for('login'))
    f = request.files.get('biene_foto')
    if f and f.filename != '':
        fname = secure_filename(f.filename)
        f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
        db.session.add(BieneImage(filename=fname))
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/biene/delete/<int:id>', methods=['POST'])
def delete_biene_image(id):
    if not session.get('admin'): return redirect(url_for('login'))
    bild = BieneImage.query.get(id)
    if bild:
        try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], bild.filename))
        except OSError: pass
        db.session.delete(bild)
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/biene/update_pos', methods=['POST'])
def update_biene_image_pos():
    if not session.get('admin'): return jsonify({'status': 'error'}), 403
    data = request.get_json() or {}
    bild = BieneImage.query.get(data.get('id'))
    if bild:
        bild.x_pos, bild.y_pos = data.get('x', bild.x_pos), data.get('y', bild.y_pos)
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 404

@app.route('/admin/postfach/delete/<int:id>', methods=['POST'])
def delete_nachricht(id):
    if not session.get('admin'): return "Unbefugt", 403
    anfrage = KontaktAnfrage.query.get(id)
    if anfrage:
        try:
            db.session.delete(anfrage)
            db.session.commit()
            flash("Nachricht erfolgreich gelöscht.", "success")
        except Exception as e:
            db.session.rollback()
            print(f"Fehler beim Löschen der Nachricht: {e}")
    return redirect(url_for('admin_postfach'))

@app.route('/admin/delete_home_image/<slot>', methods=['POST'])
def delete_home_image(slot):
    if not session.get('admin'): return "Unbefugt", 403
    if slot not in ['img1', 'img2', 'img3']: return "Ungültiger Slot", 400
    home = HomeContent.query.first()
    if home:
        filename = getattr(home, slot)
        if filename:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path): os.remove(file_path)
        setattr(home, slot, None)
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/update_cafe', methods=['POST'])
def update_cafe():
    if not session.get('admin'): return "Unbefugt", 403
    caffee = Content.query.filter_by(seite='caffee').first()
    if not caffee:
        caffee = Content(seite='caffee')
        db.session.add(caffee)
    caffee_unten = Content.query.filter_by(seite='caffee_unten').first()
    if not caffee_unten:
        caffee_unten = Content(seite='caffee_unten')
        db.session.add(caffee_unten)

    caffee.text = request.form.get('text')
    caffee_unten.text = request.form.get('text_unten')

    offen = request.form.get('cafe_offen', 'nein')
    von = request.form.get('cafe_von', '14:00')
    bis = request.form.get('cafe_bis', '18:00')
    caffee_unten.text = f"{offen}|{von}|{bis}"  # FIX: Speichern im TEXT Feld passend zum context_processor!

    file = request.files.get('cafe_banner')
    if file and file.filename != '':
        if caffee.titel and '.' in caffee.titel:
            old_path = os.path.join(app.config['UPLOAD_FOLDER'], caffee.titel)
            if os.path.exists(old_path): os.remove(old_path)
        ext = os.path.splitext(file.filename)[1]
        filename = f"cafe_banner_{uuid.uuid4().hex[:8]}{ext}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        caffee.titel = filename

    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/delete_cafe_banner', methods=['POST'])
def delete_cafe_banner():
    if not session.get('admin'): return "Unbefugt", 403
    caffee = Content.query.filter_by(seite='caffee').first()
    if caffee and caffee.titel:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], caffee.titel)
        if os.path.exists(file_path): os.remove(file_path)
        caffee.titel = "Kein Banner" 
        db.session.commit()
    return redirect(url_for('admin'))



if __name__ == '__main__':
    app.run(debug=True)