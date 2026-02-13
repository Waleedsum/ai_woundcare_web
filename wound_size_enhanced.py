"""
Enhanced Wound Size Estimation with Adaptive Calibration
Supports reference markers and improved segmentation
"""

import cv2
import numpy as np
from PIL import Image
from typing import Dict, Optional, Tuple
import math

class WoundSizeEstimator:
    """
    Advanced wound size estimation with multiple calibration methods
    """
    
    def __init__(self):
        # Default calibration factors for different image sources
        self.default_calibrations = {
            "smartphone_close": 0.008,      # ~5-10cm distance
            "smartphone_medium": 0.015,     # ~15-25cm distance
            "smartphone_far": 0.025,        # ~30-40cm distance
            "professional_camera": 0.005,   # High-resolution medical camera
            "webcam": 0.012                 # Standard webcam
        }
    
    def estimate_wound_size(
        self,
        image: Image.Image,
        reference_object_cm: Optional[float] = None,
        calibration_type: str = "smartphone_close",
        return_mask: bool = False
    ) -> Dict:
        """
        Estimate wound size with multiple methods
        
        Args:
            image: PIL Image object
            reference_object_cm: Known size of reference object in cm (if present)
            calibration_type: Type of calibration to use
            return_mask: Whether to return segmentation mask
            
        Returns:
            Dict with size_cm2, dimensions, confidence, and optional mask
        """
        
        img_array = np.array(image)
        
        # 1. Detect reference object if present
        pixels_per_cm = None
        if reference_object_cm:
            pixels_per_cm = self._detect_reference_object(img_array, reference_object_cm)
        
        # 2. Segment wound area
        wound_mask, confidence = self._segment_wound_enhanced(img_array)
        
        # 3. Calculate pixel area
        pixel_area = np.sum(wound_mask > 0)
        
        # 4. Determine calibration factor
        if pixels_per_cm:
            # Use reference object calibration (most accurate)
            calibration_factor = 1 / (pixels_per_cm ** 2)
            calibration_method = "reference_object"
        else:
            # Use default calibration based on image type
            calibration_factor = self.default_calibrations.get(
                calibration_type, 
                self.default_calibrations["smartphone_close"]
            )
            calibration_method = calibration_type
        
        # 5. Calculate size in cm²
        size_cm2 = round(pixel_area * calibration_factor, 2)
        size_cm2 = max(size_cm2, 0.1)  # Minimum 0.1 cm²
        
        # 6. Calculate wound dimensions
        dimensions = self._calculate_dimensions(wound_mask, pixels_per_cm or (1/math.sqrt(calibration_factor)))
        
        result = {
            "size_cm2": size_cm2,
            "length_cm": dimensions["length_cm"],
            "width_cm": dimensions["width_cm"],
            "pixel_area": int(pixel_area),
            "confidence": confidence,
            "calibration_method": calibration_method,
            "calibration_factor": calibration_factor
        }
        
        if return_mask:
            result["mask"] = wound_mask
        
        return result
    
    def _segment_wound_enhanced(self, img: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Enhanced wound segmentation using multiple color spaces
        Returns mask and confidence score (0-1)
        """
        
        # Convert to different color spaces
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
        lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
        
        # Method 1: HSV-based detection (good for red/pink wounds)
        # Red hue ranges
        lower_red1 = np.array([0, 40, 40])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 40, 40])
        upper_red2 = np.array([180, 255, 255])
        
        # Pink/light red ranges
        lower_pink = np.array([0, 20, 100])
        upper_pink = np.array([20, 150, 255])
        
        mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask_pink = cv2.inRange(hsv, lower_pink, upper_pink)
        hsv_mask = mask_red1 | mask_red2 | mask_pink
        
        # Method 2: LAB-based detection (good for varying lighting)
        # Target red/pink in LAB space (high A value)
        lower_lab = np.array([20, 130, 0])
        upper_lab = np.array([255, 255, 255])
        lab_mask = cv2.inRange(lab, lower_lab, upper_lab)
        
        # Method 3: RGB channel analysis
        red_channel = img[:, :, 0]
        green_channel = img[:, :, 1]
        
        # Wound typically has R > G
        rg_diff = red_channel.astype(np.int16) - green_channel.astype(np.int16)
        rgb_mask = (rg_diff > 15).astype(np.uint8) * 255
        
        # Combine masks with weights
        combined_mask = np.zeros_like(hsv_mask, dtype=np.float32)
        combined_mask += hsv_mask.astype(np.float32) * 0.4
        combined_mask += lab_mask.astype(np.float32) * 0.4
        combined_mask += rgb_mask.astype(np.float32) * 0.2
        
        # Threshold combined mask
        combined_mask = (combined_mask > 127).astype(np.uint8) * 255
        
        # Morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)
        
        # Calculate confidence based on mask consistency
        confidence = self._calculate_segmentation_confidence(
            hsv_mask, lab_mask, rgb_mask, combined_mask
        )
        
        return combined_mask, confidence
    
    def _calculate_segmentation_confidence(
        self,
        mask1: np.ndarray,
        mask2: np.ndarray,
        mask3: np.ndarray,
        final_mask: np.ndarray
    ) -> float:
        """
        Calculate confidence score based on agreement between methods
        """
        
        # Convert to binary
        m1 = (mask1 > 0).astype(int)
        m2 = (mask2 > 0).astype(int)
        m3 = (mask3 > 0).astype(int)
        
        # Calculate intersection over union for each pair
        def iou(a, b):
            intersection = np.sum(a & b)
            union = np.sum(a | b)
            return intersection / union if union > 0 else 0
        
        iou_12 = iou(m1, m2)
        iou_13 = iou(m1, m3)
        iou_23 = iou(m2, m3)
        
        # Average IoU as confidence
        avg_iou = (iou_12 + iou_13 + iou_23) / 3
        
        # Penalize very small or very large detections
        final_area = np.sum(final_mask > 0)
        image_area = final_mask.shape[0] * final_mask.shape[1]
        area_ratio = final_area / image_area
        
        if area_ratio < 0.01 or area_ratio > 0.7:
            confidence_penalty = 0.7
        else:
            confidence_penalty = 1.0
        
        confidence = avg_iou * confidence_penalty
        
        return round(confidence, 3)
    
    def _detect_reference_object(
        self,
        img: np.ndarray,
        known_size_cm: float
    ) -> Optional[float]:
        """
        Detect reference object (e.g., ruler, coin) and calculate pixels per cm
        
        Currently detects circular objects (coins, markers)
        """
        
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        
        # Use Hough Circle Transform to detect circular reference objects
        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=50,
            param1=50,
            param2=30,
            minRadius=20,
            maxRadius=200
        )
        
        if circles is not None:
            circles = np.round(circles[0, :]).astype(int)
            
            # Assume largest circle is reference object
            largest_circle = max(circles, key=lambda c: c[2])  # c[2] is radius
            
            diameter_pixels = largest_circle[2] * 2
            pixels_per_cm = diameter_pixels / known_size_cm
            
            return pixels_per_cm
        
        return None
    
    def _calculate_dimensions(
        self,
        mask: np.ndarray,
        pixels_per_cm: float
    ) -> Dict[str, float]:
        """
        Calculate length and width of wound from mask
        """
        
        # Find contours
        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        if not contours:
            return {"length_cm": 0.0, "width_cm": 0.0, "perimeter_cm": 0.0}
        
        # Get largest contour (main wound)
        main_contour = max(contours, key=cv2.contourArea)
        
        # Fit minimum area rectangle
        rect = cv2.minAreaRect(main_contour)
        width_px, height_px = rect[1]
        
        # Length is the longer dimension
        length_px = max(width_px, height_px)
        width_px = min(width_px, height_px)
        
        # Convert to cm
        length_cm = round(length_px / pixels_per_cm, 2)
        width_cm = round(width_px / pixels_per_cm, 2)
        
        # Calculate perimeter
        perimeter_px = cv2.arcLength(main_contour, True)
        perimeter_cm = round(perimeter_px / pixels_per_cm, 2)
        
        return {
            "length_cm": length_cm,
            "width_cm": width_cm,
            "perimeter_cm": perimeter_cm
        }


# Example usage
if __name__ == "__main__":
    # Test with a sample image
    test_image_path = "/path/to/wound/image.jpg"
    
    try:
        image = Image.open(test_image_path)
        estimator = WoundSizeEstimator()
        
        # Without reference object
        result1 = estimator.estimate_wound_size(
            image,
            calibration_type="smartphone_close"
        )
        
        print("Estimation without reference:")
        print(f"Size: {result1['size_cm2']} cm²")
        print(f"Dimensions: {result1['length_cm']} × {result1['width_cm']} cm")
        print(f"Confidence: {result1['confidence']:.2%}")
        print(f"Method: {result1['calibration_method']}\n")
        
        # With reference object (e.g., 2.5 cm coin)
        result2 = estimator.estimate_wound_size(
            image,
            reference_object_cm=2.5,
            return_mask=True
        )
        
        print("Estimation with reference object:")
        print(f"Size: {result2['size_cm2']} cm²")
        print(f"Dimensions: {result2['length_cm']} × {result2['width_cm']} cm")
        print(f"Confidence: {result2['confidence']:.2%}")
        print(f"Method: {result2['calibration_method']}")
        
    except Exception as e:
        print(f"Error: {e}")
