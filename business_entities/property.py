# business_entities/property.py

class Property:
    def __init__(
        self,
        id: int,
        title: str | None,
        address: str | None,
        neighborhood: str | None,
        city: str | None,
        property_type: str | None,
        ambientes: int | None,
        dormitorios: int | None,
        banos: int | None,
        m2_total: float | None,
        m2_cover: float | None,
        price: float | None,
        currency: str | None,
        expensas: float | None,
        expensas_currency: str | None,
        source: str | None,
        portal_id: str | None,
        url: str | None,
        listing_type: str | None,
        status: str | None,
        text_for_embedding: str | None = None,
    ):
        self.id                 = id
        self.title              = title
        self.address            = address
        self.neighborhood       = neighborhood
        self.city               = city
        self.property_type      = property_type
        self.ambientes          = ambientes
        self.dormitorios        = dormitorios
        self.banos              = banos
        self.m2_total           = m2_total
        self.m2_cover           = m2_cover
        self.price              = price
        self.currency           = currency
        self.expensas           = expensas
        self.expensas_currency  = expensas_currency
        self.source             = source
        self.portal_id          = portal_id
        self.url                = url
        self.listing_type       = listing_type
        self.status             = status
        self.text_for_embedding = text_for_embedding

    def to_dict(self) -> dict:
        return self.__dict__