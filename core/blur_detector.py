from utils.logger import get_logger


class BlurDetector:
    @staticmethod
    def laplacian_variance(image) -> float:
        try:
            import cv2
        except ImportError:
            return 0.0
        if image is None or image.size == 0:
            return 0.0
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        return cv2.Laplacian(gray, cv2.CV_64F).var()

    @staticmethod
    def is_blurry(image: np.ndarray, threshold: float = 100.0) -> bool:
        return BlurDetector.laplacian_variance(image) < threshold

    @staticmethod
    def variance_from_path(path: str) -> float:
        try:
            import cv2
        except ImportError:
            return 0.0
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE) if 'cv2' in dir() else None
        if img is None:
            return 0.0
        try:
            import cv2
        except ImportError:
            return 0.0
        return cv2.Laplacian(img, cv2.CV_64F).var()
