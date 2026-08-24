"""
Reference tables for Tunisia's administrative hierarchy, loaded ONCE from the
GeoJSON files (tun_admin2/3/4.geojson) via scripts/init_geo_reference.py.

Mapping confirmed from the source files:
  Gouvernorat -> tun_admin2.geojson (24 features, property 'adm2_name')
  Delegation  -> tun_admin3.geojson (264 features, property 'adm3_name')
  Secteur     -> tun_admin4.geojson (2084 features, property 'adm4_name')

Every measurement row (RSRP / HTTP attempt / HTTP failure) is spatially joined
against `Sector.geom` to resolve gouvernorat/delegation/secteur in one shot,
since tun_admin4 features already carry their parent adm2_name/adm3_name.
"""
from sqlalchemy import Column, Integer, String, ForeignKey, Float
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry

from app.database import Base


class Gouvernorat(Base):
    __tablename__ = "ref_gouvernorat"

    id = Column(Integer, primary_key=True)
    pcode = Column(String(20), unique=True, nullable=False)   # e.g. TN11
    name = Column(String(100), nullable=False, index=True)     # adm2_name
    geom = Column(Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=True)

    delegations = relationship("Delegation", back_populates="gouvernorat")


class Delegation(Base):
    __tablename__ = "ref_delegation"

    id = Column(Integer, primary_key=True)
    pcode = Column(String(20), unique=True, nullable=False)   # e.g. TN1151
    name = Column(String(100), nullable=False, index=True)     # adm3_name
    gouvernorat_id = Column(Integer, ForeignKey("ref_gouvernorat.id"), nullable=False)
    geom = Column(Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=True)

    gouvernorat = relationship("Gouvernorat", back_populates="delegations")
    secteurs = relationship("Secteur", back_populates="delegation")


class Secteur(Base):
    __tablename__ = "ref_secteur"

    id = Column(Integer, primary_key=True)
    pcode = Column(String(20), unique=True, nullable=False)   # e.g. TN115151
    name = Column(String(100), nullable=False, index=True)     # adm4_name = "Site Name"
    delegation_id = Column(Integer, ForeignKey("ref_delegation.id"), nullable=False)
    # Denormalized for fast lookups/archiving without joining up the chain every time
    gouvernorat_name = Column(String(100), nullable=False)
    delegation_name = Column(String(100), nullable=False)
    center_lat = Column(Float, nullable=True)
    center_lon = Column(Float, nullable=True)
    geom = Column(Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=True)

    delegation = relationship("Delegation", back_populates="secteurs")
