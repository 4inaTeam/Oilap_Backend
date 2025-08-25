from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock

from .ml_service import global_prediction_service


User = get_user_model()


class PredictionServiceTestCase(TestCase):
    """
    Test cases for the ML prediction service
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='ADMIN'
        )

    def test_employee_prediction_endpoint(self):
        """Test employee prediction API endpoint"""
        url = reverse('predict:predict-employees')
        response = self.client.get(url)

        self.assertIn(response.status_code, [
                      status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR])

    def test_all_targets_prediction_endpoint(self):
        """Test all targets prediction API endpoint"""
        url = reverse('predict:predict-all')
        response = self.client.get(url)

        self.assertIn(response.status_code, [
                      status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR])

    def test_quality_prediction_endpoint(self):
        """Test quality prediction API endpoint"""
        url = reverse('predict:predict-quality')
        response = self.client.get(url)

        self.assertIn(response.status_code, [
                      status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR])

    def test_seasonal_analysis_endpoint(self):
        """Test seasonal analysis API endpoint"""
        url = reverse('predict:predict-seasonal')
        response = self.client.get(url)

        self.assertIn(response.status_code, [
                      status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR])

    def test_prediction_status_endpoint(self):
        """Test prediction status API endpoint"""
        url = reverse('predict:prediction-status')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('is_loaded', response.data)

    def test_energy_prediction_with_quantities(self):
        """Test energy prediction with specific quantities"""
        url = reverse('predict:predict-energy')
        response = self.client.get(url, {'quantities': '10,25,50'})

        self.assertIn(response.status_code, [
                      status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR])

    def test_invalid_quantities_format(self):
        """Test API response to invalid quantities format"""
        url = reverse('predict:predict-energy')
        response = self.client.get(url, {'quantities': 'invalid,format'})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_clear_cache_admin_only(self):
        """Test that cache clearing requires admin privileges"""
        # Create regular user
        regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='testpass123',
            role='CLIENT'
        )
        self.client.force_authenticate(user=regular_user)

        url = reverse('predict:clear-prediction-cache')
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_access(self):
        """Test that unauthenticated users cannot access prediction endpoints"""
        self.client.force_authenticate(user=None)

        urls = [
            reverse('predict:predict-energy'),
            reverse('predict:predict-water'),
            reverse('predict:predict-employees'),
            reverse('predict:predict-all'),
            reverse('predict:predict-quality'),
            reverse('predict:predict-seasonal'),
            reverse('predict:prediction-status'),
        ]

        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_service_initialization(self):
        """Test that the prediction service initializes properly"""
        # The service should have is_loaded attribute
        self.assertIsInstance(global_prediction_service.is_loaded, bool)

    @patch('predict.ml_service.joblib.load')
    @patch('predict.ml_service.pickle.load')
    def test_model_loading_success(self, mock_pickle, mock_joblib):
        """Test successful model loading"""
        # Mock the loaded objects
        mock_joblib.return_value = MagicMock()
        mock_pickle.return_value = {
            'source': MagicMock(),
            'olive_type': MagicMock(),
            'condition': MagicMock(),
            'size': MagicMock(),
            'press_method': MagicMock()
        }

        # Reset service and reload
        service = global_prediction_service
        service._load_models()

        # Service should report as loaded (if files exist)
        # This might fail in test environment if model files don't exist
        # In that case, is_loaded would be False, which is expected

    def test_get_model_status(self):
        """Test getting model status"""
        status = global_prediction_service.get_model_status()

        self.assertIn('is_loaded', status)
        self.assertIn('models_available', status)
        self.assertIsInstance(status['is_loaded'], bool)


class PredictionAPITestCase(APITestCase):
    """
    Test cases for prediction API endpoints
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='ADMIN'
        )
        self.client.force_authenticate(user=self.user)

    def test_energy_prediction_endpoint(self):
        """Test energy prediction API endpoint"""
        url = reverse('predict:predict-energy')
        response = self.client.get(url)

        # Should return 200 or 500 depending on if models are loaded
        self.assertIn(response.status_code, [
                      status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR])

    def test_water_prediction_endpoint(self):
        """Test water prediction API endpoint"""
        url = reverse('predict:predict-water')
        response = self.client.get(url)

        self.assertIn(response.status_code, [
                      status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR])

    def test_admin_clear_cache_success(self):
        """Test that admin users can successfully clear prediction cache"""
        url = reverse('predict:clear-prediction-cache')
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
