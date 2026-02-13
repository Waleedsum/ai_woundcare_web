"""
Enhanced Infection Risk Scoring System
Incorporates tissue composition, wound characteristics, and clinical indicators
"""

import numpy as np
from typing import Dict, Optional

class InfectionRiskCalculator:
    """
    Multi-factor infection risk assessment
    Score range: 0-10 (higher = greater risk)
    """
    
    # Clinical risk factors and their weights
    KEYWORD_WEIGHTS = {
        "purulent": 2.0,
        "pus": 2.0,
        "foul odor": 1.8,
        "malodorous": 1.8,
        "necrotic": 1.5,
        "black eschar": 1.5,
        "fever": 1.2,
        "warmth": 1.0,
        "erythema": 1.0,
        "swelling": 0.8,
        "pain": 0.6,
        "slough": 0.5,
        "delayed healing": 0.5,
        "friable": 0.7,
        "bleeding": 0.6
    }
    
    def calculate_risk(
        self,
        clinical_text: str,
        tissue_counts: Dict[str, float],
        wound_size_cm2: float,
        exudate_level: str,
        days_since_onset: Optional[int] = None,
        patient_factors: Optional[Dict[str, bool]] = None
    ) -> Dict[str, float]:
        """
        Calculate comprehensive infection risk score
        
        Args:
            clinical_text: Clinical notes/observations
            tissue_counts: Dict with tissue percentages (granulation_percent, slough_percent, necrotic_percent)
            wound_size_cm2: Wound area in cm²
            exudate_level: "none", "light", "moderate", "heavy"
            days_since_onset: Days since wound appeared
            patient_factors: Dict of risk factors (diabetes, immunosuppressed, poor_circulation, etc.)
            
        Returns:
            Dict with total_score, subscores, and risk_level
        """
        
        # 1. TEXT-BASED CLINICAL INDICATORS (0-3 points)
        text_score = self._calculate_text_score(clinical_text)
        
        # 2. TISSUE COMPOSITION SCORE (0-3 points)
        tissue_score = self._calculate_tissue_score(tissue_counts)
        
        # 3. EXUDATE SCORE (0-2 points)
        exudate_score = self._calculate_exudate_score(exudate_level, tissue_counts)
        
        # 4. WOUND SIZE FACTOR (0-1 point)
        size_score = self._calculate_size_score(wound_size_cm2)
        
        # 5. CHRONICITY FACTOR (0-1 point)
        chronicity_score = self._calculate_chronicity_score(days_since_onset)
        
        # 6. PATIENT RISK FACTORS (0-2 points)
        patient_score = self._calculate_patient_score(patient_factors)
        
        # Calculate total score (max 12, normalized to 10)
        raw_total = (
            text_score + 
            tissue_score + 
            exudate_score + 
            size_score + 
            chronicity_score + 
            patient_score
        )
        
        # Normalize to 0-10 scale
        total_score = min(round((raw_total / 12) * 10, 1), 10.0)
        
        # Determine risk level
        risk_level = self._determine_risk_level(total_score)
        
        return {
            "total_score": total_score,
            "risk_level": risk_level,
            "subscores": {
                "clinical_indicators": round(text_score, 2),
                "tissue_composition": round(tissue_score, 2),
                "exudate": round(exudate_score, 2),
                "wound_size": round(size_score, 2),
                "chronicity": round(chronicity_score, 2),
                "patient_factors": round(patient_score, 2)
            },
            "interpretation": self._generate_interpretation(total_score, tissue_counts)
        }
    
    def _calculate_text_score(self, text: str) -> float:
        """Score based on clinical keywords (max 3.0)"""
        text_lower = text.lower()
        score = 0.0
        
        for keyword, weight in self.KEYWORD_WEIGHTS.items():
            if keyword in text_lower:
                score += weight
        
        return min(score, 3.0)
    
    def _calculate_tissue_score(self, tissue_counts: Dict[str, float]) -> float:
        """Score based on tissue composition (max 3.0)"""
        necrotic_pct = tissue_counts.get("necrotic_percent", 0)
        slough_pct = tissue_counts.get("slough_percent", 0)
        granulation_pct = tissue_counts.get("granulation_percent", 0)
        
        score = 0.0
        
        # Necrotic tissue is highest risk
        if necrotic_pct > 50:
            score += 2.5
        elif necrotic_pct > 25:
            score += 1.5
        elif necrotic_pct > 10:
            score += 0.8
        
        # Slough indicates biofilm/infection risk
        if slough_pct > 60:
            score += 1.5
        elif slough_pct > 30:
            score += 0.8
        elif slough_pct > 10:
            score += 0.4
        
        # Lack of granulation is concerning
        if granulation_pct < 20:
            score += 0.5
        
        return min(score, 3.0)
    
    def _calculate_exudate_score(self, exudate_level: str, tissue_counts: Dict) -> float:
        """Score based on exudate characteristics (max 2.0)"""
        exudate_lower = exudate_level.lower()
        
        base_score = {
            "none": 0.0,
            "light": 0.3,
            "moderate": 0.8,
            "heavy": 1.5
        }.get(exudate_lower, 0.5)
        
        # Heavy exudate with necrotic tissue is especially concerning
        necrotic_pct = tissue_counts.get("necrotic_percent", 0)
        if exudate_lower == "heavy" and necrotic_pct > 30:
            base_score += 0.5
        
        return min(base_score, 2.0)
    
    def _calculate_size_score(self, wound_size_cm2: float) -> float:
        """Larger wounds have higher infection risk (max 1.0)"""
        if wound_size_cm2 > 50:
            return 1.0
        elif wound_size_cm2 > 25:
            return 0.7
        elif wound_size_cm2 > 10:
            return 0.4
        elif wound_size_cm2 > 5:
            return 0.2
        else:
            return 0.0
    
    def _calculate_chronicity_score(self, days_since_onset: Optional[int]) -> float:
        """Chronic wounds have higher infection risk (max 1.0)"""
        if days_since_onset is None:
            return 0.0
        
        if days_since_onset > 90:  # 3+ months
            return 1.0
        elif days_since_onset > 30:  # 1-3 months
            return 0.6
        elif days_since_onset > 14:  # 2-4 weeks
            return 0.3
        else:
            return 0.0
    
    def _calculate_patient_score(self, patient_factors: Optional[Dict[str, bool]]) -> float:
        """Score based on patient risk factors (max 2.0)"""
        if not patient_factors:
            return 0.0
        
        score = 0.0
        
        # High-risk conditions
        if patient_factors.get("diabetes", False):
            score += 0.6
        if patient_factors.get("immunosuppressed", False):
            score += 0.8
        if patient_factors.get("poor_circulation", False):
            score += 0.5
        if patient_factors.get("smoking", False):
            score += 0.3
        if patient_factors.get("malnutrition", False):
            score += 0.4
        if patient_factors.get("incontinence", False):
            score += 0.3
        if patient_factors.get("recent_antibiotics", False):
            score += 0.2
        
        return min(score, 2.0)
    
    def _determine_risk_level(self, score: float) -> str:
        """Categorize infection risk"""
        if score < 2.5:
            return "Low Risk"
        elif score < 5.0:
            return "Moderate Risk"
        elif score < 7.5:
            return "High Risk"
        else:
            return "Critical Risk"
    
    def _generate_interpretation(self, score: float, tissue_counts: Dict) -> str:
        """Generate human-readable interpretation"""
        necrotic = tissue_counts.get("necrotic_percent", 0)
        slough = tissue_counts.get("slough_percent", 0)
        
        if score < 2.5:
            return "Wound shows minimal signs of infection. Continue routine monitoring."
        elif score < 5.0:
            interp = "Moderate infection risk detected. "
            if slough > 40:
                interp += "Significant slough present - consider enhanced cleansing. "
            interp += "Monitor closely for progression."
            return interp
        elif score < 7.5:
            interp = "High infection risk. "
            if necrotic > 30:
                interp += "Necrotic tissue requires debridement. "
            interp += "Consider wound culture and increased monitoring frequency."
            return interp
        else:
            return "Critical infection risk. Immediate clinical evaluation recommended. Consider antibiotic therapy and surgical consultation."


# Example usage
if __name__ == "__main__":
    calculator = InfectionRiskCalculator()
    
    # Test case 1: Low risk
    result1 = calculator.calculate_risk(
        clinical_text="Pink granulation tissue visible, minimal drainage",
        tissue_counts={"granulation_percent": 80, "slough_percent": 15, "necrotic_percent": 5},
        wound_size_cm2=3.5,
        exudate_level="light",
        days_since_onset=10,
        patient_factors={"diabetes": False, "immunosuppressed": False}
    )
    print("Test Case 1 (Low Risk):")
    print(f"Score: {result1['total_score']}/10")
    print(f"Level: {result1['risk_level']}")
    print(f"Subscores: {result1['subscores']}")
    print(f"Interpretation: {result1['interpretation']}\n")
    
    # Test case 2: High risk
    result2 = calculator.calculate_risk(
        clinical_text="Purulent drainage with foul odor, necrotic tissue present, surrounding erythema",
        tissue_counts={"granulation_percent": 10, "slough_percent": 40, "necrotic_percent": 50},
        wound_size_cm2=28.5,
        exudate_level="heavy",
        days_since_onset=45,
        patient_factors={"diabetes": True, "immunosuppressed": False, "poor_circulation": True}
    )
    print("Test Case 2 (High Risk):")
    print(f"Score: {result2['total_score']}/10")
    print(f"Level: {result2['risk_level']}")
    print(f"Subscores: {result2['subscores']}")
    print(f"Interpretation: {result2['interpretation']}")
