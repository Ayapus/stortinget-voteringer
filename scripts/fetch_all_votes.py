#!/usr/bin/env python3
import os
import requests
import json
import logging
from datetime import datetime
import xml.etree.ElementTree as ET

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def fetch_all_sessions_since_2022():
    """
    Hent alle sesjoner fra 2022 til nå.
    """
    current_year = datetime.now().year
    sessions = []
    
    for year in range(2022, current_year + 2):
        sessions.append(f"{year}-{year+1}")
    
    return sessions

def fetch_saker_from_session(sesjon):
    """
    Hent alle saker fra en sesjon.
    """
    url = f"https://data.stortinget.no/eksport/saker?sesjonid={sesjon}"
    
    logging.info(f"Henter saker fra sesjon {sesjon}")
    
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        
        root = ET.fromstring(resp.content)
        ns = {'ns': 'http://data.stortinget.no'}
        
        sak_ids = []
        for sak in root.findall('.//ns:sak', ns):
            sak_id_elem = sak.find('ns:id', ns)
            if sak_id_elem is not None and sak_id_elem.text:
                sak_ids.append(sak_id_elem.text)
        
        logging.info(f"Fant {len(sak_ids)} saker i {sesjon}")
        return sak_ids
        
    except Exception as e:
        logging.error(f"Feil ved henting av saker fra {sesjon}: {e}")
        return []

def fetch_voteringer_for_sak(sak_id):
    """
    Hent alle voteringer for en sak.
    """
    url = f"https://data.stortinget.no/eksport/voteringer?sakid={sak_id}"
    
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        
        root = ET.fromstring(resp.content)
        ns = {'ns': 'http://data.stortinget.no'}
        
        votes = []
        for votering in root.findall('.//ns:sak_votering', ns):
            vote_data = {}
            
            # Hent dato fra votering_resultat hvis den finnes der
            resultat = votering.find('ns:votering_resultat', ns)
            if resultat is not None:
                dato_elem = resultat.find('ns:votering_dato_tid', ns)
                if dato_elem is not None:
                    vote_data['votering_tid'] = dato_elem.text
            
            # Hent andre felter
            for field in ['votering_id', 'antall_for', 'antall_mot', 'vedtatt', 
                         'votering_tema', 'sak_id']:
                elem = votering.find(f'ns:{field}', ns)
                if elem is not None:
                    vote_data[field] = elem.text
            
            # Hvis vi fortsatt ikke har tid, prøv votering_tid direkte
            if 'votering_tid' not in vote_data:
                tid_elem = votering.find('ns:votering_tid', ns)
                if tid_elem is not None:
                    vote_data['votering_tid'] = tid_elem.text
            
            if vote_data and vote_data.get('votering_id'):
                votes.append(vote_data)
        
        return votes
        
    except Exception as e:
        return []

def fetch_vote_details(votering_id):
    """
    Hent individuelle stemmer OG riktig dato for en votering.
    """
    url = f"https://data.stortinget.no/eksport/votering?voteringid={votering_id}"
    
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        
        root = ET.fromstring(resp.content)
        ns = {'ns': 'http://data.stortinget.no'}
        
        # Hent riktig dato
        dato_tid = None
        dato_elem = root.find('.//ns:votering_dato_tid', ns)
        if dato_elem is not None:
            dato_tid = dato_elem.text
        
        # Hent stemmer
        stemmer = []
        for stemme in root.findall('.//ns:representant_votering', ns):
            representant_elem = stemme.find('ns:representant', ns)
            if representant_elem is not None:
                fornavn_elem = representant_elem.find('ns:fornavn', ns)
                etternavn_elem = representant_elem.find('ns:etternavn', ns)
                parti_elem = representant_elem.find('ns:parti', ns)
                
                fornavn = fornavn_elem.text if fornavn_elem is not None else ""
                etternavn = etternavn_elem.text if etternavn_elem is not None else ""
                parti_id = parti_elem.find('ns:id', ns).text if parti_elem is not None and parti_elem.find('ns:id', ns) is not None else ""
            
            stemme_elem = stemme.find('ns:votering_resultat', ns)
            if stemme_elem is not None:
                resultat_elem = stemme_elem.find('ns:id', ns)
                stemme_resultat = resultat_elem.text if resultat_elem is not None else ""
            else:
                stemme_resultat = ""
            
            stemmer.append({
                "navn": f"{fornavn} {etternavn}".strip(),
                "parti": parti_id,
                "stemme": stemme_resultat
            })
        
        return {"stemmer": stemmer, "dato_tid": dato_tid}
        
    except Exception as e:
        logging.debug(f"Kunne ikke hente detaljer for votering {votering_id}: {e}")
        return {"stemmer": [], "dato_tid": None}

def fetch_sak_details(sak_id):
    """
    Hent detaljer om en sak.
    """
    url = f"https://data.stortinget.no/eksport/sak?sakid={sak_id}"
    
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        
        root = ET.fromstring(resp.content)
        ns = {'ns': 'http://data.stortinget.no'}
        
        tittel_elem = root.find('.//ns:tittel', ns)
        korttittel_elem = root.find('.//ns:korttittel', ns)
        
        tittel = korttittel_elem.text if korttittel_elem is not None and korttittel_elem.text else None
        if not tittel:
            tittel = tittel_elem.text if tittel_elem is not None else None
        
        return tittel
        
    except Exception as e:
        return None

def fetch_all_votes():
    """
    Hent alle voteringer fra 2022 til nå.
    """
    sessions = fetch_all_sessions_since_2022()
    all_votes = []
    
    for sesjon in sessions:
        sak_ids = fetch_saker_from_session(sesjon)
        
        # Hent voteringer fra alle saker i denne sesjonen
        for i, sak_id in enumerate(sak_ids):
            if i % 50 == 0:
                logging.info(f"  Behandler sak {i+1}/{len(sak_ids)} i {sesjon}")
            
            votes = fetch_voteringer_for_sak(sak_id)
            
            for vote in votes:
                # Hent sakstittel
                sakstittel = fetch_sak_details(vote.get('sak_id', ''))
                
                # Hent individuelle stemmer OG riktig dato
                votering_id = vote.get('votering_id', '')
                detaljer = fetch_vote_details(votering_id)
                stemmer = detaljer["stemmer"]
                riktig_dato = detaljer["dato_tid"]
                
                # Bruk riktig dato hvis vi fant den
                votering_tid = riktig_dato if riktig_dato else vote.get('votering_tid', '')
                
                vote_obj = {
                    "id": votering_id,
                    "tema": vote.get('votering_tema', 'Ukjent'),
                    "sakstittel": sakstittel,
                    "for": int(vote.get('antall_for', 0)) if vote.get('antall_for') not in [None, '-1'] else 0,
                    "mot": int(vote.get('antall_mot', 0)) if vote.get('antall_mot') not in [None, '-1'] else 0,
                    "vedtatt": vote.get('vedtatt', '').lower() == 'true',
                    "sak_id": vote.get('sak_id', ''),
                    "tid": votering_tid if votering_tid else datetime.now().isoformat(),
                    "stemmer": stemmer
                }
                
                if not votering_tid:
                    logging.warning(f"Mangler tid for votering {votering_id}")
                
                all_votes.append(vote_obj)
    
    # Sorter etter tid (nyeste først)
    all_votes.sort(key=lambda x: x['tid'], reverse=True)
    
    logging.info(f"Totalt {len(all_votes)} voteringer funnet")
    return all_votes

def save_to_json(votes):
    """
    Lagre voteringer til JSON-fil.
    """
    output_dir = "public/data"
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, "votes.json")
    
    data = {
        "siste_oppdatering": datetime.now().isoformat(),
        "antall_voteringer": len(votes),
        "voteringer": votes
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logging.info(f"Data lagret til {output_file}")

def main():
    logging.info("Starter henting av alle voteringer...")
    votes = fetch_all_votes()
    
    if votes:
        save_to_json(votes)
        logging.info("Ferdig!")
    else:
        logging.warning("Ingen voteringer funnet")

if __name__ == "__main__":
    main()