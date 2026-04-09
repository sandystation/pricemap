from sqlalchemy.ext.asyncio import AsyncSession

from src.ml.comparables import ComparableFinder
from src.ml.confidence import ConfidenceScorer
from src.ml.predictor import PricePredictor
from src.schemas.valuation import ValuationRequest, ValuationResponse
from src.services.geocoding_service import GeocodingService


class ValuationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.predictor = PricePredictor()
        self.comparables = ComparableFinder(db)
        self.confidence = ConfidenceScorer(db)
        self.geocoder = GeocodingService()

    async def estimate(self, request: ValuationRequest) -> ValuationResponse:
        # Step 1: Geocode if needed
        lat, lon = request.lat, request.lon
        if not lat or not lon:
            if not request.address:
                raise ValueError("Either lat/lon or address must be provided")
            geo = await self.geocoder.geocode(
                address=request.address, country_code=request.country_code
            )
            lat, lon = geo.lat, geo.lon

        # Step 2: Find comparables
        comparable_properties = await self.comparables.find(
            country_code=request.country_code,
            lat=lat,
            lon=lon,
            property_type=request.property_type.value,
            area_sqm=request.area_sqm,
        )

        # Step 3: Score confidence
        confidence_score = await self.confidence.score(
            country_code=request.country_code,
            lat=lat,
            lon=lon,
            num_comparables=len(comparable_properties),
            request=request,
        )

        # Step 4: Predict price
        prediction = self.predictor.predict(
            country_code=request.country_code,
            lat=lat,
            lon=lon,
            property_type=request.property_type.value,
            area_sqm=request.area_sqm,
            floor=request.floor,
            rooms=request.rooms,
            bedrooms=request.bedrooms,
            year_built=request.year_built,
            condition=request.condition.value if request.condition else None,
            comparables=comparable_properties,
            confidence_score=confidence_score,
        )

        # Determine confidence label
        if confidence_score >= 75:
            confidence_label = "High"
        elif confidence_score >= 50:
            confidence_label = "Moderate"
        else:
            confidence_label = "Low"

        return ValuationResponse(
            estimate_eur=prediction["estimate"],
            confidence_low=prediction["low"],
            confidence_high=prediction["high"],
            confidence_score=confidence_score,
            confidence_label=confidence_label,
            price_per_sqm=prediction["estimate"] / request.area_sqm,
            comparables=comparable_properties,
            feature_importance=prediction.get("feature_importance", {}),
            model_version=prediction.get("model_version", "comparables_v1"),
            data_freshness=prediction.get("data_freshness"),
            method=prediction.get("method", "comparables"),
        )
