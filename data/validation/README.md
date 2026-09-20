# Noordin Top Dark Network Validation Dataset

**SIH26189GREEN** | AI-Powered Criminal Network Analysis System  
**Track:** Ministry of Home Affairs — Software / Blockchain & Cybersecurity

---

## 1. Source & Authority

* **Dataset Title**: *Roberts and Everton Terrorist Data: Noordin Top Terrorist Network (Subset)*
* **Compilers**: Professor Nancy Roberts, Professor Sean F. Everton, and Daniel Cunningham
* **Institutional Affiliation**: CORE Lab, Department of Defense Analysis, Naval Postgraduate School (NPS), Monterey, California.
* **Primary Source Document**: International Crisis Group (2006). *Terrorism in Indonesia: Noordin's Networks*. Asia Report N°114.
* **Academic Reference**: Everton, Sean F. (2012). *Disrupting Dark Networks*. Structural Analysis in the Social Sciences. Cambridge University Press.
* **Permanent DOI**: [10.17605/OSF.IO/ZMB9C](https://doi.org/10.17605/OSF.IO/ZMB9C)
* **Public Data Repositories**: 
  - Open Science Framework (OSF): `https://osf.io/zmb9c/`
  - Association of Religion Data Archives (ARDA): `https://www.thearda.com/data-archive?fid=TERRNET`
  - UCINET Dark Network Data Archive: Analytic Technologies

---

## 2. Dataset Overview & Scope

The dataset maps the covert network centered on **Noordin Mohammad Top**, a key Malaysian bomb strategist and commander of Tanzim Qaidat al-Jihad, responsible for high-profile multi-perpetrator attacks in Indonesia (including the 2003 JW Marriott bombing, 2004 Australian Embassy bombing, and 2005 Bali bombings).

* **Nodes**: 79 individuals (co-conspirators, safehouse providers, couriers, bomb-makers, facilitators, and religious mentors).
* **Adjacency Structure**: 1-mode multi-relational network.
* **Graph Type**: Undirected, multi-layered social and operational ties.

---

## 3. Relationship Definitions & CSV Files

The dataset relationships are partitioned into four standardized edge lists conforming to the schema:
```csv
source,target,relationship,confidence,source_reference
```

### 3.1 `communication_edges.csv`
* **Definition**: Verified bilateral communications between operatives, including recorded phone calls, courier message deliveries, and face-to-face operational planning meetings.
* **Example Ties**: 
  - `Noordin Mohammad Top` $\leftrightarrow$ `Subur Sugiarto` (courier / messenger coordination)
  - `Azahari Husin` $\leftrightarrow$ `Cholily` (bomb-maker courier link)
* **Confidence**: 1.0 (Direct evidentiary basis from ICG investigative report No. 114).

### 3.2 `operational_edges.csv`
* **Definition**: Physical cooperation in criminal acts, including bomb fabrication, safehouse harborage, weapons procurement/transport, and target reconnaissance.
* **Example Ties**:
  - `Noordin Mohammad Top` $\leftrightarrow$ `Azahari Husin` (joint operational command / bomb assembly)
  - `Noordin Mohammad Top` $\leftrightarrow$ `Irun Ali` (safehouse harboring and refuge)
  - `Urwah` $\leftrightarrow$ `Ahmad Basyir` (operational safehouse supply)
* **Confidence**: 1.0.

### 3.3 `trust_edges.csv`
* **Definition**: Kinship ties (marriage, siblings, in-laws) and shared trust bonds formed through long-standing pre-operational associations (e.g. mentor-peer ties at Luqmanul Hakiem madrasah).
* **Example Ties**:
  - `Irun Ali` $\leftrightarrow$ `Jabir` (brothers / kinship)
  - `Irun Ali` $\leftrightarrow$ `Fathur Rahman al-Ghozi` (family / kinship)
  - `Noordin Mohammad Top` $\leftrightarrow$ `Zarkasih` (high-trust religious command bond)
* **Confidence**: 1.0.

### 3.4 `financial_edges.csv`
* **Status**: **Header only (0 rows)**
* **Explanation**: While the broader qualitative narrative of the ICG report notes that the network utilized robbery proceeds (*fai*) and donations, the formal 79x79 CORE Lab relational matrices **do not record explicit pairwise financial transaction records** between individual actors. In strict accordance with the project rule against fabricating relationships, this file is intentionally left with 0 rows rather than inventing unsupported financial edges.

---

## 4. Provenance & Scientific Integrity

* Every included edge is grounded in the Roberts & Everton (2011) coding of the International Crisis Group Asia Report No. 114.
* No synthetic or speculative edges have been added.
* Python loader available at: [`backend/app/services/validation/noordin_loader.py`](file:///C:/Users/brije/Documents/NEXUS/backend/app/services/validation/noordin_loader.py).

---

## 5. Limitations

1. **Discovery & Retrospective Bias**: Nodes and edges were documented retrospectively following police investigations, arrests, and trials.
2. **Binary Edge Weighting**: The primary relationship matrices are unweighted (binary indicators of tie existence) rather than continuous transaction frequencies.
3. **Temporal Flattening**: Ties across an eight-year operational period (2001–2009) are represented in a unified aggregate graph.
