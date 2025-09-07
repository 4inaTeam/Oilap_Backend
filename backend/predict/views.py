from products.models import Product
from .ml_service import global_prediction_service
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import permissions, status
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from django.db.models.functions import Extract
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from decimal import Decimal
from reportlab.lib.units import cm
from reportlab.lib import colors
import logging
import json
import hashlib
import io
import base64
import numpy as np
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')


logger = logging.getLogger(__name__)


class PredictEnergyView(APIView):
    """
    API endpoint for energy consumption predictions
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        Get energy consumption predictions

        Query parameters:
        - quantities: comma-separated list of quantities (optional)
        - sources: comma-separated list of sources to include (optional)
        - use_real_data: if true, base predictions on actual product quantities
        """
        try:
            # Parse query parameters
            quantities_param = request.query_params.get('quantities', '')
            quantities_range = None

            if quantities_param:
                try:
                    quantities_range = [float(q.strip())
                                        for q in quantities_param.split(',')]
                    if any(q <= 0 for q in quantities_range):
                        return Response({
                            'error': 'All quantities must be positive numbers',
                            'success': False
                        }, status=status.HTTP_400_BAD_REQUEST)
                    if len(quantities_range) > 20:
                        return Response({
                            'error': 'Maximum 20 quantities allowed',
                            'success': False
                        }, status=status.HTTP_400_BAD_REQUEST)
                except ValueError:
                    return Response({
                        'error': 'Invalid quantities format. Use comma-separated numbers.',
                        'success': False
                    }, status=status.HTTP_400_BAD_REQUEST)

            use_real_data = request.query_params.get(
                'use_real_data', 'false').lower() == 'true'

            # If using real data, get quantities from existing products
            if use_real_data and not quantities_range:
                products = Product.objects.all()
                if products.exists():
                    # Convert kg to tons and get unique ranges
                    quantities_kg = products.values_list('quantity', flat=True)
                    quantities_range = list(
                        set([float(q)/1000 for q in quantities_kg if q > 0]))
                    quantities_range.sort()

            # Get predictions
            predictions = global_prediction_service.predict_energy_consumption(
                quantities_range=quantities_range
            )

            if predictions.get('success'):
                # Add real data comparison if available
                if use_real_data:
                    real_stats = Product.objects.filter(
                        ml_prediction_generated=True
                    ).aggregate(
                        total_predicted_energy=Sum('ml_predicted_energy_kwh'),
                        avg_predicted_energy=Avg('ml_predicted_energy_kwh'),
                        product_count=Count('id')
                    )

                    predictions['real_data_comparison'] = {
                        'products_with_ml': real_stats['product_count'] or 0,
                        'total_predicted_energy_kwh': float(real_stats['total_predicted_energy'] or 0),
                        'avg_predicted_energy_kwh': float(real_stats['avg_predicted_energy'] or 0)
                    }

                predictions['metadata'] = {
                    'timestamp': timezone.now(),
                    'user': request.user.username,
                    'used_real_data': use_real_data,
                    'quantities_analyzed': quantities_range
                }

            return Response(predictions,
                            status=status.HTTP_200_OK if predictions.get('success') else status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Error in energy prediction API: {e}")
            return Response({
                'error': f'Failed to generate energy predictions: {str(e)}',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PredictWaterView(APIView):
    """
    API endpoint for water consumption predictions
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get water consumption predictions"""
        try:
            quantities_param = request.query_params.get('quantities', '')
            quantities_range = None

            if quantities_param:
                try:
                    quantities_range = [float(q.strip())
                                        for q in quantities_param.split(',')]
                    if any(q <= 0 for q in quantities_range):
                        return Response({
                            'error': 'All quantities must be positive numbers',
                            'success': False
                        }, status=status.HTTP_400_BAD_REQUEST)
                    if len(quantities_range) > 20:
                        return Response({
                            'error': 'Maximum 20 quantities allowed',
                            'success': False
                        }, status=status.HTTP_400_BAD_REQUEST)
                except ValueError:
                    return Response({
                        'error': 'Invalid quantities format. Use comma-separated numbers.',
                        'success': False
                    }, status=status.HTTP_400_BAD_REQUEST)

            use_real_data = request.query_params.get(
                'use_real_data', 'false').lower() == 'true'

            # If using real data, get quantities from existing products
            if use_real_data and not quantities_range:
                products = Product.objects.all()
                if products.exists():
                    quantities_kg = products.values_list('quantity', flat=True)
                    quantities_range = list(
                        set([float(q)/1000 for q in quantities_kg if q > 0]))
                    quantities_range.sort()

            # Get predictions
            predictions = global_prediction_service.predict_water_consumption(
                quantities_range=quantities_range
            )

            if predictions.get('success'):
                # Add real data comparison if available
                if use_real_data:
                    real_stats = Product.objects.filter(
                        ml_prediction_generated=True
                    ).aggregate(
                        total_predicted_water=Sum('ml_predicted_water_liters'),
                        avg_predicted_water=Avg('ml_predicted_water_liters'),
                        product_count=Count('id')
                    )

                    predictions['real_data_comparison'] = {
                        'products_with_ml': real_stats['product_count'] or 0,
                        'total_predicted_water_liters': float(real_stats['total_predicted_water'] or 0),
                        'avg_predicted_water_liters': float(real_stats['avg_predicted_water'] or 0)
                    }

                predictions['metadata'] = {
                    'timestamp': timezone.now(),
                    'user': request.user.username,
                    'used_real_data': use_real_data,
                    'quantities_analyzed': quantities_range
                }

            return Response(predictions,
                            status=status.HTTP_200_OK if predictions.get('success') else status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Error in water prediction API: {e}")
            return Response({
                'error': f'Failed to generate water predictions: {str(e)}',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PredictEmployeesView(APIView):
    """
    API endpoint for employee requirements predictions
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get employee requirements predictions"""
        try:
            quantities_param = request.query_params.get('quantities', '')
            quantities_range = None

            if quantities_param:
                try:
                    quantities_range = [float(q.strip())
                                        for q in quantities_param.split(',')]
                    if any(q <= 0 for q in quantities_range):
                        return Response({
                            'error': 'All quantities must be positive numbers',
                            'success': False
                        }, status=status.HTTP_400_BAD_REQUEST)
                    if len(quantities_range) > 20:
                        return Response({
                            'error': 'Maximum 20 quantities allowed',
                            'success': False
                        }, status=status.HTTP_400_BAD_REQUEST)
                except ValueError:
                    return Response({
                        'error': 'Invalid quantities format. Use comma-separated numbers.',
                        'success': False
                    }, status=status.HTTP_400_BAD_REQUEST)

            use_real_data = request.query_params.get(
                'use_real_data', 'false').lower() == 'true'

            # If using real data, get quantities from existing products
            if use_real_data and not quantities_range:
                products = Product.objects.all()
                if products.exists():
                    quantities_kg = products.values_list('quantity', flat=True)
                    quantities_range = list(
                        set([float(q)/1000 for q in quantities_kg if q > 0]))
                    quantities_range.sort()

            # Get predictions
            predictions = global_prediction_service.predict_employee_requirements(
                quantities_range=quantities_range
            )

            if predictions.get('success'):
                # Add real data comparison if available
                if use_real_data:
                    real_stats = Product.objects.filter(
                        ml_prediction_generated=True
                    ).aggregate(
                        total_predicted_employees=Sum(
                            'ml_predicted_employees'),
                        avg_predicted_employees=Avg('ml_predicted_employees'),
                        product_count=Count('id')
                    )

                    predictions['real_data_comparison'] = {
                        'products_with_ml': real_stats['product_count'] or 0,
                        'total_predicted_employees': int(real_stats['total_predicted_employees'] or 0),
                        'avg_predicted_employees': float(real_stats['avg_predicted_employees'] or 0)
                    }

                predictions['metadata'] = {
                    'timestamp': timezone.now(),
                    'user': request.user.username,
                    'used_real_data': use_real_data,
                    'quantities_analyzed': quantities_range
                }

            return Response(predictions,
                            status=status.HTTP_200_OK if predictions.get('success') else status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Error in employee prediction API: {e}")
            return Response({
                'error': f'Failed to generate employee predictions: {str(e)}',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PredictAllView(APIView):
    """
    API endpoint for simultaneous multi-target predictions
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get predictions for all main targets simultaneously"""
        try:
            quantities_param = request.query_params.get('quantities', '')
            quantities_range = None

            if quantities_param:
                try:
                    quantities_range = [float(q.strip())
                                        for q in quantities_param.split(',')]
                    if any(q <= 0 for q in quantities_range):
                        return Response({
                            'error': 'All quantities must be positive numbers',
                            'success': False
                        }, status=status.HTTP_400_BAD_REQUEST)
                    if len(quantities_range) > 20:
                        return Response({
                            'error': 'Maximum 20 quantities allowed',
                            'success': False
                        }, status=status.HTTP_400_BAD_REQUEST)
                except ValueError:
                    return Response({
                        'error': 'Invalid quantities format. Use comma-separated numbers.',
                        'success': False
                    }, status=status.HTTP_400_BAD_REQUEST)

            use_real_data = request.query_params.get(
                'use_real_data', 'false').lower() == 'true'
            include_correlations = request.query_params.get(
                'include_correlations', 'true').lower() == 'true'

            # If using real data, get quantities from existing products
            if use_real_data and not quantities_range:
                products = Product.objects.all()
                if products.exists():
                    quantities_kg = products.values_list('quantity', flat=True)
                    quantities_range = list(
                        set([float(q)/1000 for q in quantities_kg if q > 0]))
                    quantities_range.sort()

            # Get all predictions
            predictions = global_prediction_service.predict_all_targets(
                quantities_range=quantities_range
            )

            if predictions.get('success'):
                # Add real data comparison if available
                if use_real_data:
                    real_stats = Product.objects.filter(
                        ml_prediction_generated=True
                    ).aggregate(
                        total_energy=Sum('ml_predicted_energy_kwh'),
                        total_water=Sum('ml_predicted_water_liters'),
                        total_employees=Sum('ml_predicted_employees'),
                        avg_energy=Avg('ml_predicted_energy_kwh'),
                        avg_water=Avg('ml_predicted_water_liters'),
                        avg_employees=Avg('ml_predicted_employees'),
                        product_count=Count('id')
                    )

                    predictions['real_data_comparison'] = {
                        'products_with_ml': real_stats['product_count'] or 0,
                        'totals': {
                            'energy_kwh': float(real_stats['total_energy'] or 0),
                            'water_liters': float(real_stats['total_water'] or 0),
                            'employees': int(real_stats['total_employees'] or 0)
                        },
                        'averages': {
                            'energy_kwh': float(real_stats['avg_energy'] or 0),
                            'water_liters': float(real_stats['avg_water'] or 0),
                            'employees': float(real_stats['avg_employees'] or 0)
                        }
                    }

                # Add efficiency analysis
                if predictions.get('main_targets'):
                    main_targets = predictions['main_targets']
                    predictions['efficiency_analysis'] = {
                        'energy_efficiency': {
                            'kwh_per_scenario': main_targets['energy_kwh']['mean'],
                            'total_energy_estimate': main_targets['energy_kwh']['total_estimated']
                        },
                        'water_efficiency': {
                            'liters_per_scenario': main_targets['water_liters']['mean'],
                            'total_water_estimate': main_targets['water_liters']['total_estimated']
                        },
                        'labor_efficiency': {
                            'employees_per_scenario': main_targets['employees']['mean'],
                            'total_employees_estimate': main_targets['employees']['total_estimated']
                        }
                    }

                predictions['metadata'] = {
                    'timestamp': timezone.now(),
                    'user': request.user.username,
                    'used_real_data': use_real_data,
                    'quantities_analyzed': quantities_range,
                    'include_correlations': include_correlations
                }

            return Response(predictions,
                            status=status.HTTP_200_OK if predictions.get('success') else status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Error in all targets prediction API: {e}")
            return Response({
                'error': f'Failed to generate all targets predictions: {str(e)}',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PredictQualityView(APIView):
    """
    API endpoint for oil quality predictions
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get oil quality predictions"""
        try:
            quantities_param = request.query_params.get('quantities', '')
            quantities_range = None

            if quantities_param:
                try:
                    quantities_range = [float(q.strip())
                                        for q in quantities_param.split(',')]
                    if any(q <= 0 for q in quantities_range):
                        return Response({
                            'error': 'All quantities must be positive numbers',
                            'success': False
                        }, status=status.HTTP_400_BAD_REQUEST)
                    if len(quantities_range) > 20:
                        return Response({
                            'error': 'Maximum 20 quantities allowed',
                            'success': False
                        }, status=status.HTTP_400_BAD_REQUEST)
                except ValueError:
                    return Response({
                        'error': 'Invalid quantities format. Use comma-separated numbers.',
                        'success': False
                    }, status=status.HTTP_400_BAD_REQUEST)

            use_real_data = request.query_params.get(
                'use_real_data', 'false').lower() == 'true'

            # If using real data, get quantities from existing products
            if use_real_data and not quantities_range:
                products = Product.objects.all()
                if products.exists():
                    quantities_kg = products.values_list('quantity', flat=True)
                    quantities_range = list(
                        set([float(q)/1000 for q in quantities_kg if q > 0]))
                    quantities_range.sort()

            # Get quality predictions
            predictions = global_prediction_service.predict_quality(
                quantities_range=quantities_range
            )

            if predictions.get('success'):
                # Add real data comparison if available
                if use_real_data:
                    # Get actual quality distribution from products
                    quality_distribution = Product.objects.values('quality').annotate(
                        count=Count('id')
                    )

                    # Get quality statistics
                    quality_stats = {}
                    total_products = Product.objects.count()

                    for item in quality_distribution:
                        quality_stats[item['quality']] = {
                            'count': item['count'],
                            'percentage': round((item['count'] / total_products * 100), 2) if total_products > 0 else 0
                        }

                    predictions['real_data_comparison'] = {
                        'actual_quality_distribution': quality_stats,
                        'total_products': total_products
                    }

                # Add quality insights
                if 'quality_predictions' in predictions:
                    quality_data = predictions['quality_predictions']
                    predictions['quality_insights'] = {
                        'quality_range': quality_data['max_score'] - quality_data['min_score'],
                        'quality_variability': 'High' if quality_data['std_score'] > 10 else 'Medium' if quality_data['std_score'] > 5 else 'Low',
                        'average_quality_category': self._categorize_quality_score(quality_data['mean_score'])
                    }

                predictions['metadata'] = {
                    'timestamp': timezone.now(),
                    'user': request.user.username,
                    'used_real_data': use_real_data,
                    'quantities_analyzed': quantities_range
                }

            return Response(predictions,
                            status=status.HTTP_200_OK if predictions.get('success') else status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Error in quality prediction API: {e}")
            return Response({
                'error': f'Failed to generate quality predictions: {str(e)}',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _categorize_quality_score(self, score):
        """Categorize quality score into readable categories"""
        if score >= 90:
            return 'excellent'
        elif score >= 80:
            return 'good'
        elif score >= 70:
            return 'average'
        else:
            return 'poor'


class PredictSeasonalView(APIView):
    """
    API endpoint for seasonal predictive analysis
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get seasonal analysis and predictions"""
        try:
            include_monthly = request.query_params.get(
                'include_monthly', 'false').lower() == 'true'

            # Get seasonal analysis
            analysis = global_prediction_service.seasonal_analysis()

            if analysis.get('success'):
                # Add real seasonal data if available
                try:
                    seasonal_real_data = self._get_real_seasonal_data()
                    analysis['real_seasonal_data'] = seasonal_real_data

                    # Add seasonal comparison
                    if seasonal_real_data:
                        analysis['seasonal_comparison'] = self._compare_seasonal_data(
                            analysis.get('seasonal_patterns', {}),
                            seasonal_real_data
                        )

                except Exception as e:
                    logger.warning(f"Could not fetch real seasonal data: {e}")

                # Add monthly breakdown if requested
                if include_monthly:
                    monthly_data = self._get_monthly_breakdown()
                    analysis['monthly_breakdown'] = monthly_data

                # Add seasonal recommendations
                if 'seasonal_patterns' in analysis:
                    analysis['detailed_recommendations'] = self._generate_seasonal_recommendations(
                        analysis['seasonal_patterns']
                    )

                analysis['metadata'] = {
                    'timestamp': timezone.now(),
                    'user': request.user.username,
                    'analysis_type': 'seasonal_prediction',
                    'include_monthly': include_monthly
                }

            return Response(analysis,
                            status=status.HTTP_200_OK if analysis.get('success') else status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Error in seasonal analysis API: {e}")
            return Response({
                'error': f'Failed to generate seasonal analysis: {str(e)}',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _get_real_seasonal_data(self):
        """Get real seasonal data from products"""
        seasonal_real_data = {}

        # Define seasons by month
        season_months = {
            'spring': [3, 4, 5],
            'summer': [6, 7, 8],
            'autumn': [9, 10, 11],
            'winter': [12, 1, 2]
        }

        for season, months in season_months.items():
            season_products = Product.objects.filter(
                created_at__month__in=months,
                ml_prediction_generated=True
            ).aggregate(
                count=Count('id'),
                avg_energy=Avg('ml_predicted_energy_kwh'),
                avg_water=Avg('ml_predicted_water_liters'),
                avg_employees=Avg('ml_predicted_employees'),
                total_quantity=Sum('quantity')
            )

            seasonal_real_data[season] = {
                'products_count': season_products['count'] or 0,
                'avg_energy_kwh': float(season_products['avg_energy'] or 0),
                'avg_water_liters': float(season_products['avg_water'] or 0),
                'avg_employees': float(season_products['avg_employees'] or 0),
                'total_quantity_kg': float(season_products['total_quantity'] or 0)
            }

        return seasonal_real_data

    def _get_monthly_breakdown(self):
        """Get monthly breakdown of production data"""
        monthly_data = {}

        for month in range(1, 13):
            month_products = Product.objects.filter(
                created_at__month=month,
                ml_prediction_generated=True
            ).aggregate(
                count=Count('id'),
                avg_energy=Avg('ml_predicted_energy_kwh'),
                avg_water=Avg('ml_predicted_water_liters'),
                avg_employees=Avg('ml_predicted_employees')
            )

            month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                           'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

            monthly_data[month_names[month-1]] = {
                'products_count': month_products['count'] or 0,
                'avg_energy_kwh': float(month_products['avg_energy'] or 0),
                'avg_water_liters': float(month_products['avg_water'] or 0),
                'avg_employees': float(month_products['avg_employees'] or 0)
            }

        return monthly_data

    def _compare_seasonal_data(self, predicted_patterns, real_data):
        """Compare predicted vs real seasonal data"""
        comparison = {}

        for season in predicted_patterns.keys():
            if season in real_data:
                predicted = predicted_patterns[season]
                real = real_data[season]

                comparison[season] = {
                    'energy_difference': predicted.get('energy_kwh', 0) - real.get('avg_energy_kwh', 0),
                    'water_difference': predicted.get('water_liters', 0) - real.get('avg_water_liters', 0),
                    'employee_difference': predicted.get('employees', 0) - real.get('avg_employees', 0),
                    'accuracy_score': self._calculate_accuracy_score(predicted, real)
                }

        return comparison

    def _calculate_accuracy_score(self, predicted, real):
        """Calculate a simple accuracy score between predicted and real data"""
        try:
            energy_accuracy = 1 - abs(predicted.get('energy_kwh', 0) - real.get(
                'avg_energy_kwh', 0)) / max(predicted.get('energy_kwh', 1), real.get('avg_energy_kwh', 1))
            water_accuracy = 1 - abs(predicted.get('water_liters', 0) - real.get('avg_water_liters', 0)) / max(
                predicted.get('water_liters', 1), real.get('avg_water_liters', 1))
            employee_accuracy = 1 - abs(predicted.get('employees', 0) - real.get(
                'avg_employees', 0)) / max(predicted.get('employees', 1), real.get('avg_employees', 1))

            return round((energy_accuracy + water_accuracy + employee_accuracy) / 3 * 100, 2)
        except (ZeroDivisionError, TypeError):
            return 0

    def _generate_seasonal_recommendations(self, seasonal_patterns):
        """Generate detailed seasonal recommendations"""
        recommendations = {}

        try:
            # Find best seasons for each metric
            best_energy = min(seasonal_patterns.items(),
                              key=lambda x: x[1].get('energy_kwh', float('inf')))
            best_quality = max(seasonal_patterns.items(),
                               key=lambda x: x[1].get('quality_score', 0))
            best_efficiency = max(seasonal_patterns.items(),
                                  key=lambda x: x[1].get('employees', 0))

            recommendations['optimal_planning'] = {
                'energy_efficiency': {
                    'best_season': best_energy[0],
                    'savings_potential': f"{(max(s.get('energy_kwh', 0) for s in seasonal_patterns.values()) - best_energy[1].get('energy_kwh', 0)):.1f} kWh",
                    'recommendation': f"Schedule high-volume production in {best_energy[0]} for maximum energy efficiency"
                },
                'quality_optimization': {
                    'best_season': best_quality[0],
                    'quality_advantage': f"+{(best_quality[1].get('quality_score', 0) - min(s.get('quality_score', 0) for s in seasonal_patterns.values())):.1f} points",
                    'recommendation': f"Focus on premium oil production during {best_quality[0]} season"
                },
                'resource_planning': {
                    'peak_season': best_efficiency[0],
                    'staffing_recommendation': f"Plan for {best_efficiency[1].get('employees', 0):.0f} employees during peak season",
                    'recommendation': f"Optimize workforce allocation for {best_efficiency[0]} production cycles"
                }
            }
        except Exception as e:
            logger.warning(f"Error generating seasonal recommendations: {e}")
            recommendations['optimal_planning'] = {
                'energy_efficiency': {'best_season': 'autumn', 'recommendation': 'Unable to determine best season'},
                'quality_optimization': {'best_season': 'autumn', 'recommendation': 'Unable to determine best season'},
                'resource_planning': {'peak_season': 'autumn', 'recommendation': 'Unable to determine peak season'}
            }

        return recommendations


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def prediction_status(request):
    """
    Get status of the prediction service and model information
    """
    try:
        service_status = global_prediction_service.get_model_status()

        # Add system performance metrics
        if service_status['is_loaded']:
            # Test a simple prediction to check response time
            import time
            start_time = time.time()
            try:
                test_result = global_prediction_service.predict_energy_consumption(
                    quantities_range=[10])
                response_time = time.time() - start_time
                service_status['performance'] = {
                    'last_test_response_time_ms': round(response_time * 1000, 2),
                    'test_successful': test_result.get('success', False)
                }
            except Exception:
                service_status['performance'] = {
                    'last_test_response_time_ms': None,
                    'test_successful': False
                }

        # Add cache statistics
        cache_stats = {
            'cache_backend': cache.__class__.__name__,
            'default_timeout': getattr(cache, 'default_timeout', 300),
            'cache_prefix': getattr(cache, 'key_prefix', '')
        }

        service_status.update({
            'timestamp': timezone.now(),
            'user': request.user.username,
            'cache_info': cache_stats,
            'endpoints_available': [
                '/api/predict/energy/',
                '/api/predict/water/',
                '/api/predict/employees/',
                '/api/predict/all/',
                '/api/predict/quality/',
                '/api/predict/seasonal/'
            ]
        })

        return Response(service_status, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error getting prediction status: {e}")
        return Response({
            'error': f'Failed to get prediction status: {str(e)}',
            'success': False
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def clear_prediction_cache(request):
    """
    Clear prediction cache (admin/employee only)
    """
    try:
        if not hasattr(request.user, 'role') or request.user.role not in ['ADMIN', 'EMPLOYEE']:
            return Response({
                'error': 'Only admins and employees can clear prediction cache',
                'success': False
            }, status=status.HTTP_403_FORBIDDEN)

        # Get cache keys to clear from request body
        clear_all = request.data.get('clear_all', False)
        specific_keys = request.data.get('specific_keys', [])

        cleared_count = 0

        if clear_all:
            # Clear all cache - use with caution in production
            cache.clear()
            cleared_count = 1  # We can't count exact keys cleared with clear()
            message = "All cache cleared"
        else:
            # Clear specific prediction cache patterns
            cache_patterns = specific_keys if specific_keys else [
                'enhanced_predict_energy_',
                'enhanced_predict_water_',
                'enhanced_predict_employees_',
                'enhanced_predict_all_',
                'enhanced_predict_quality_',
                'enhanced_seasonal_analysis'
            ]

            for pattern in cache_patterns:
                # In production, you'd want more sophisticated cache key management
                # This is a simplified approach
                if pattern == 'enhanced_seasonal_analysis':
                    if cache.delete(pattern):
                        cleared_count += 1
                else:
                    # For patterns, you might need to iterate through cache keys
                    # This is a placeholder - implement based on your cache backend
                    cache.delete(pattern)
                    cleared_count += 1

            message = f"Cleared {len(cache_patterns)} cache patterns"

        return Response({
            'message': message,
            'cache_keys_cleared': cleared_count,
            'cleared_by': request.user.username,
            'timestamp': timezone.now(),
            'success': True
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error clearing prediction cache: {e}")
        return Response({
            'error': f'Failed to clear prediction cache: {str(e)}',
            'success': False
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def reload_models(request):
    """
    Reload ML models (admin only)
    """
    try:
        if not hasattr(request.user, 'role') or request.user.role != 'ADMIN':
            return Response({
                'error': 'Only admins can reload ML models',
                'success': False
            }, status=status.HTTP_403_FORBIDDEN)

        # Clear cache first
        cache.clear()

        # Reload the global prediction service
        global_prediction_service._load_enhanced_models()

        reload_status = {
            'models_reloaded': global_prediction_service.is_loaded,
            'timestamp': timezone.now(),
            'reloaded_by': request.user.username,
            'model_status': global_prediction_service.get_model_status()
        }

        if global_prediction_service.is_loaded:
            return Response({
                'message': 'ML models reloaded successfully',
                'reload_status': reload_status,
                'success': True
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'message': 'Failed to reload ML models - check model files',
                'reload_status': reload_status,
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        logger.error(f"Error reloading ML models: {e}")
        return Response({
            'error': f'Failed to reload ML models: {str(e)}',
            'success': False
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def prediction_health(request):
    """
    Health check endpoint for the prediction service
    """
    try:
        health_status = {
            'service': 'Enhanced ML Prediction API',
            'status': 'healthy' if global_prediction_service.is_loaded else 'unhealthy',
            'timestamp': timezone.now(),
            'version': '2.0.0',
            'checks': {}
        }

        # Check model loading
        health_status['checks']['models_loaded'] = {
            'status': 'pass' if global_prediction_service.is_loaded else 'fail',
            'details': global_prediction_service.get_model_status()
        }

        # Check cache availability
        try:
            cache.set('health_check', 'test', timeout=60)
            cache_test = cache.get('health_check')
            cache.delete('health_check')

            health_status['checks']['cache'] = {
                'status': 'pass' if cache_test == 'test' else 'fail',
                'backend': cache.__class__.__name__
            }
        except Exception as e:
            health_status['checks']['cache'] = {
                'status': 'fail',
                'error': str(e)
            }

        # Check database connectivity (through Product model)
        try:
            product_count = Product.objects.count()
            health_status['checks']['database'] = {
                'status': 'pass',
                'products_count': product_count
            }
        except Exception as e:
            health_status['checks']['database'] = {
                'status': 'fail',
                'error': str(e)
            }

        # Test prediction functionality
        if global_prediction_service.is_loaded:
            try:
                import time
                start_time = time.time()
                test_result = global_prediction_service.predict_energy_consumption(
                    quantities_range=[10])
                response_time = time.time() - start_time

                health_status['checks']['prediction_test'] = {
                    'status': 'pass' if test_result.get('success') else 'fail',
                    'response_time_ms': round(response_time * 1000, 2),
                    'test_result': test_result.get('success', False)
                }
            except Exception as e:
                health_status['checks']['prediction_test'] = {
                    'status': 'fail',
                    'error': str(e)
                }
        else:
            health_status['checks']['prediction_test'] = {
                'status': 'skip',
                'reason': 'Models not loaded'
            }

        # Overall health determination
        failed_checks = [
            check for check in health_status['checks'].values() if check['status'] == 'fail']
        if failed_checks:
            health_status['status'] = 'unhealthy'
            health_status['failed_checks_count'] = len(failed_checks)

        return Response(health_status, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error in prediction health check: {e}")
        return Response({
            'service': 'Enhanced ML Prediction API',
            'status': 'error',
            'timestamp': timezone.now(),
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



def create_waste_partition_chart(fitoura_amount, margin_amount):
    """
    Create a pie chart showing the partition of waste (Fitoura vs Margin)
    """
    try:
        if fitoura_amount <= 0 and margin_amount <= 0:
            raise ValueError("No waste data available")

        data = [fitoura_amount, margin_amount]
        labels = ['Déchet Fitoura', 'Déchet Margin']
        colors = ['#FF6B6B', '#4ECDC4']

        plt.figure(figsize=(8, 6))
        fig, ax = plt.subplots(figsize=(8, 6))

        wedges, texts, autotexts = ax.pie(
            data,
            labels=labels,
            autopct='%1.1f%%',
            startangle=90,
            colors=colors,
            explode=(0.05, 0.05)  # Slight separation for better visibility
        )

        ax.set_title('Répartition des Déchets',
                     fontsize=14, fontweight='bold', pad=20)

        # Style the text
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(11)

        for text in texts:
            text.set_fontsize(10)
            text.set_fontweight('bold')

        # Add total waste info
        total_waste = fitoura_amount + margin_amount
        plt.figtext(0.5, 0.02, f'Total des Déchets: {total_waste:.2f} kg',
                    ha='center', fontsize=10, style='italic')

        plt.tight_layout()

        # Convert to base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150,
                    bbox_inches='tight', facecolor='white')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        plt.close()

        return image_base64

    except Exception as e:
        logger.error(f"Error creating waste partition chart: {e}")
        return create_error_chart(f"Erreur Graphique Déchets:\n{str(e)}")


def create_cost_distribution_chart(costs_dict):
    """
    Create a pie chart showing the distribution of different costs
    """
    try:
        # Extract cost values
        electricity_cost = costs_dict.get('electricity_cost_tnd', 0)
        water_cost = costs_dict.get('water_cost_tnd', 0)
        labor_cost = costs_dict.get('labor_cost_tnd', 0)

        # Filter out zero costs
        cost_data = []
        cost_labels = []
        if electricity_cost > 0:
            cost_data.append(electricity_cost)
            cost_labels.append('Coût Électricité')
        if water_cost > 0:
            cost_data.append(water_cost)
            cost_labels.append('Coût Eau')
        if labor_cost > 0:
            cost_data.append(labor_cost)
            cost_labels.append('Coût Main d\'Œuvre')

        if not cost_data:
            raise ValueError("No cost data available")

        colors = ['#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8']

        plt.figure(figsize=(8, 6))
        fig, ax = plt.subplots(figsize=(8, 6))

        wedges, texts, autotexts = ax.pie(
            cost_data,
            labels=cost_labels,
            autopct='%1.1f%%',
            startangle=45,
            colors=colors[:len(cost_data)],
            explode=[0.02] * len(cost_data)  # Small separation
        )

        ax.set_title('Répartition des Coûts Opérationnels',
                     fontsize=14, fontweight='bold', pad=20)

        # Style the text
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(11)

        for text in texts:
            text.set_fontsize(10)
            text.set_fontweight('bold')

        # Add total cost info
        total_cost = sum(cost_data)
        plt.figtext(0.5, 0.02, f'Coût Total: {total_cost:.2f} TND',
                    ha='center', fontsize=10, style='italic')

        plt.tight_layout()

        # Convert to base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150,
                    bbox_inches='tight', facecolor='white')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        plt.close()

        return image_base64

    except Exception as e:
        logger.error(f"Error creating cost distribution chart: {e}")
        return create_error_chart(f"Erreur Graphique Coûts:\n{str(e)}")


def create_actual_vs_predicted_chart(product, predictions, traditional_metrics):
    """
    Create a line chart comparing actual data vs predicted data
    """
    try:
        # Prepare data for comparison
        metrics = []
        actual_values = []
        predicted_values = []

        # Get actual data from product (if available)
        if hasattr(product, 'ml_predicted_energy_kwh') and product.ml_predicted_energy_kwh:
            metrics.append('Énergie (kWh)')
            actual_values.append(float(product.ml_predicted_energy_kwh))
            predicted_values.append(predictions.get(
                'production', {}).get('energy_consumption_kwh', 0))

        if hasattr(product, 'ml_predicted_water_liters') and product.ml_predicted_water_liters:
            metrics.append('Eau (L)')
            actual_values.append(float(product.ml_predicted_water_liters))
            predicted_values.append(predictions.get(
                'production', {}).get('water_consumption_liters', 0))

        if hasattr(product, 'ml_predicted_employees') and product.ml_predicted_employees:
            metrics.append('Employés')
            actual_values.append(float(product.ml_predicted_employees))
            predicted_values.append(predictions.get(
                'production', {}).get('total_employees', 0))

        # If no actual ML data, create comparison with traditional calculations
        if not metrics and traditional_metrics.get('success'):
            metrics = [
                'Coût Eau (TND)', 'Coût Énergie (TND)', 'Coût M.O. (TND)']
            actual_values = [
                traditional_metrics.get('cout_eau', 0),
                traditional_metrics.get('cout_energetique', 0),
                traditional_metrics.get('cout_main_oeuvre', 0)
            ]
            predicted_values = [
                predictions.get('costs', {}).get('water_cost_tnd', 0),
                predictions.get('costs', {}).get('electricity_cost_tnd', 0),
                predictions.get('costs', {}).get('labor_cost_tnd', 0)
            ]

        if not metrics or len(metrics) < 2:
            raise ValueError("Insufficient data for comparison")

        fig, ax = plt.subplots(figsize=(10, 6))

        x = np.arange(len(metrics))
        width = 0.35

        # Create bars
        bars1 = ax.bar(x - width/2, actual_values, width, label='Données Actuelles',
                       color='#2E86C1', alpha=0.8)
        bars2 = ax.bar(x + width/2, predicted_values, width, label='Prédictions ML',
                       color='#E74C3C', alpha=0.8)

        # Add value labels on bars
        for bar in bars1:
            height = bar.get_height()
            ax.annotate(f'{height:.1f}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=9, fontweight='bold')

        for bar in bars2:
            height = bar.get_height()
            ax.annotate(f'{height:.1f}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=9, fontweight='bold')

        ax.set_xlabel('Métriques', fontsize=12)
        ax.set_ylabel('Valeurs', fontsize=12)
        ax.set_title('Comparaison: Données Actuelles vs Prédictions ML',
                     fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(metrics, rotation=45, ha='right')
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Calculate and display accuracy
        if len(actual_values) == len(predicted_values):
            errors = [abs(a - p) / max(a, 1) * 100 for a,
                      p in zip(actual_values, predicted_values)]
            avg_accuracy = 100 - np.mean(errors)
            ax.text(0.02, 0.98, f'Précision Moyenne: {avg_accuracy:.1f}%',
                    transform=ax.transAxes, fontsize=10,
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        plt.tight_layout()

        # Convert to base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150,
                    bbox_inches='tight', facecolor='white')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        plt.close()

        return image_base64

    except Exception as e:
        logger.error(f"Error creating actual vs predicted chart: {e}")
        return create_error_chart(f"Erreur Comparaison:\n{str(e)}")


def create_error_chart(error_message):
    """Create a simple error chart when chart generation fails"""
    try:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, error_message, horizontalalignment='center',
                verticalalignment='center', transform=ax.transAxes,
                fontsize=12, bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.7))
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150,
                    bbox_inches='tight', facecolor='white')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        plt.close()

        return image_base64
    except:
        return None


def calculate_oil_production_metrics(quantity, quality, source):
    """
    Calculate oil production metrics based on product inputs
    Enhanced version with better error handling
    """
    try:
        quantity = float(quantity) if quantity else 0
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        quality = str(quality).lower().strip() if quality else 'moyenne'

        # Enhanced mappings
        oil_yield_map = {
            'excellente': 0.20, 'excellent': 0.20,
            'bonne': 0.18, 'good': 0.18,
            'moyenne': 0.17, 'average': 0.17,
            'mauvaise': 0.15, 'poor': 0.15, 'bad': 0.15,
        }

        waste_coefficients = {
            'excellente': 0.82, 'excellent': 0.82,
            'bonne': 0.835, 'good': 0.835,
            'moyenne': 0.85, 'average': 0.85,
            'mauvaise': 0.875, 'poor': 0.875, 'bad': 0.875,
        }

        quality_price_map = {
            'excellente': 15.0, 'excellent': 15.0,
            'bonne': 12.0, 'good': 12.0,
            'moyenne': 10.0, 'average': 10.0,
            'mauvaise': 8.0, 'poor': 8.0, 'bad': 8.0,
        }

        oil_yield = oil_yield_map.get(quality, 0.17)
        waste_coefficient = waste_coefficients.get(quality, 0.85)
        oil_price_per_liter = quality_price_map.get(quality, 10.0)

        # Calculate metrics
        oil_quantity = quantity * oil_yield
        total_waste = quantity * waste_coefficient

        fitoura_percentage = 0.65
        dechet_fitoura = total_waste * fitoura_percentage
        dechet_margin = total_waste * (1 - fitoura_percentage)

        # Enhanced cost calculations with regional factors
        regional_factors = {
            'nord': 1.1, 'north': 1.1,
            'centre': 1.0, 'center': 1.0,
            'sud': 0.9, 'south': 0.9,
            'sfax': 1.05
        }

        source_lower = source.lower() if source else 'centre'
        regional_factor = 1.0
        for region, factor in regional_factors.items():
            if region in source_lower:
                regional_factor = factor
                break

        cout_main_oeuvre = quantity * 0.8 * regional_factor
        cout_eau = oil_quantity * 2.5 * regional_factor
        cout_energetique = quantity * 1.2 * regional_factor
        temps_pression = quantity * 0.02

        cout_total = cout_main_oeuvre + cout_eau + cout_energetique

        return {
            'qualite_oil': quality.title(),
            'quantite_oil': round(oil_quantity, 2),
            'dechet_fitoura': round(dechet_fitoura, 2),
            'dechet_margin': round(dechet_margin, 2),
            'prix_litre': oil_price_per_liter,
            'cout_main_oeuvre': round(cout_main_oeuvre, 2),
            'cout_eau': round(cout_eau, 2),
            'cout_energetique': round(cout_energetique, 2),
            'temps_pression': round(temps_pression, 2),
            'cout_total': round(cout_total, 2),
            'regional_factor': regional_factor,
            'success': True
        }

    except Exception as e:
        logger.error(f"Error calculating oil production metrics: {e}")
        return {'error': str(e), 'success': False}


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_prediction_pdf(request, product_id):
    """
    Generate enhanced PDF prediction report with charts and ML predictions
    """
    try:
        # Get the product
        try:
            product = get_object_or_404(Product, id=product_id)
        except:
            return Response({
                'error': 'Product not found',
                'success': False
            }, status=status.HTTP_404_NOT_FOUND)

        if not global_prediction_service.is_loaded:
            return Response({
                'error': 'ML service not available',
                'success': False
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # Get enhanced predictions using the new method
        predictions = global_prediction_service.predict_costs_and_production(
            source=product.source or 'Centre',
            quantity=product.quantity,
            quality=product.quality
        )

        if not predictions:
            return Response({
                'error': 'Unable to generate predictions for this product',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Get traditional calculations for comparison
        traditional_metrics = calculate_oil_production_metrics(
            product.quantity, product.quality, product.source
        )

        # Create PDF
        response = HttpResponse(content_type='application/pdf')
        response[
            'Content-Disposition'] = f'attachment; filename="enhanced_prediction_report_product_{product.id}.pdf"'

        doc = SimpleDocTemplate(response, pagesize=A4,
                                topMargin=2*cm, bottomMargin=2*cm)
        story = []
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        )

        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=15,
            textColor=colors.darkgreen
        )

        # Title
        story.append(Paragraph(
            f"Rapport de Prédiction Avancé - Produit #{product.id}", title_style))
        story.append(Spacer(1, 20))

        # Product Information
        story.append(Paragraph("Informations du Produit", subtitle_style))

        product_info = [
            ['Propriété', 'Valeur'],
            ['ID Produit', str(product.id)],
            ['Quantité', f"{product.quantity} kg"],
            ['Qualité', product.quality],
            ['Source', product.source or 'Non spécifié'],
            ['Date de Création', product.created_at.strftime(
                '%Y-%m-%d %H:%M') if hasattr(product, 'created_at') else 'N/A']
        ]

        product_table = Table(product_info, colWidths=[6*cm, 8*cm])
        product_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
        ]))

        story.append(product_table)
        story.append(Spacer(1, 30))

        # Charts Section
        story.append(Paragraph("Analyses Graphiques", subtitle_style))

        charts_created = 0

        # 1. Waste Partition Chart
        if traditional_metrics and traditional_metrics.get('success'):
            try:
                fitoura = traditional_metrics.get('dechet_fitoura', 0)
                margin = traditional_metrics.get('dechet_margin', 0)

                if fitoura > 0 or margin > 0:
                    story.append(
                        Paragraph("Répartition des Déchets", styles['Heading3']))
                    waste_chart_base64 = create_waste_partition_chart(
                        fitoura, margin)

                    if waste_chart_base64:
                        waste_chart_img = Image(io.BytesIO(
                            base64.b64decode(waste_chart_base64)))
                        waste_chart_img.drawWidth = 400
                        waste_chart_img.drawHeight = 300
                        story.append(waste_chart_img)
                        story.append(Spacer(1, 20))
                        charts_created += 1
            except Exception as e:
                logger.warning(f"Could not create waste chart: {e}")

        # 2. Cost Distribution Chart
        if predictions and 'costs' in predictions:
            try:
                story.append(
                    Paragraph("Répartition des Coûts", styles['Heading3']))
                cost_chart_base64 = create_cost_distribution_chart(
                    predictions['costs'])

                if cost_chart_base64:
                    cost_chart_img = Image(io.BytesIO(
                        base64.b64decode(cost_chart_base64)))
                    cost_chart_img.drawWidth = 400
                    cost_chart_img.drawHeight = 300
                    story.append(cost_chart_img)
                    story.append(Spacer(1, 20))
                    charts_created += 1
            except Exception as e:
                logger.warning(f"Could not create cost chart: {e}")

        # 3. Actual vs Predicted Chart
        try:
            story.append(
                Paragraph("Comparaison: Données Actuelles vs Prédictions", styles['Heading3']))
            comparison_chart_base64 = create_actual_vs_predicted_chart(
                product, predictions, traditional_metrics)

            if comparison_chart_base64:
                comparison_chart_img = Image(io.BytesIO(
                    base64.b64decode(comparison_chart_base64)))
                comparison_chart_img.drawWidth = 500
                comparison_chart_img.drawHeight = 300
                story.append(comparison_chart_img)
                story.append(Spacer(1, 20))
                charts_created += 1
        except Exception as e:
            logger.warning(f"Could not create comparison chart: {e}")

        # ML Predictions Section
        if predictions:
            story.append(
                Paragraph("Prédictions Machine Learning", subtitle_style))

            # Cost predictions
            if 'costs' in predictions:
                story.append(
                    Paragraph("Prédictions de Coûts", styles['Heading3']))
                costs = predictions['costs']

                cost_data = [
                    ['Type de Coût', 'Montant (TND)'],
                    ['Coût Électricité',
                        f"{costs.get('electricity_cost_tnd', 0):.2f}"],
                    ['Coût Eau', f"{costs.get('water_cost_tnd', 0):.2f}"],
                    ['Coût Main d\'Œuvre',
                        f"{costs.get('labor_cost_tnd', 0):.2f}"],
                    ['Coût Total Opérationnel',
                        f"{costs.get('total_operational_cost_tnd', 0):.2f}"]
                ]

                cost_table = Table(cost_data, colWidths=[7*cm, 4*cm])
                cost_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.lightgreen),
                ]))

                story.append(cost_table)
                story.append(Spacer(1, 20))

            # Production predictions
            if 'production' in predictions:
                story.append(
                    Paragraph("Prédictions de Production", styles['Heading3']))
                production = predictions['production']

                production_data = [
                    ['Métrique de Production', 'Valeur Prédite'],
                    ['Score Qualité Huile',
                        f"{production.get('oil_quality_score', 0):.1f}/100"],
                    ['Quantité Huile',
                        f"{production.get('oil_quantity_tons', 0):.2f} tonnes"],
                    ['Temps de Traitement',
                        f"{production.get('processing_time_hours', 0):.1f} heures"],
                    ['Consommation Énergie',
                        f"{production.get('energy_consumption_kwh', 0):.1f} kWh"],
                    ['Consommation Eau',
                        f"{production.get('water_consumption_liters', 0):.1f} litres"],
                    ['Employés Requis',
                        f"{production.get('total_employees', 0)} employés"]
                ]

                production_table = Table(
                    production_data, colWidths=[7*cm, 4*cm])
                production_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.darkorange),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.moccasin),
                ]))

                story.append(production_table)
                story.append(Spacer(1, 20))

        # Traditional Analysis Section
        if traditional_metrics and traditional_metrics.get('success'):
            story.append(Paragraph("Analyse Traditionnelle", subtitle_style))

            traditional_data = [
                ['Métrique', 'Valeur'],
                ['Quantité d\'Huile',
                    f"{traditional_metrics.get('quantite_oil', 0)} L"],
                ['Déchet Fitoura',
                    f"{traditional_metrics.get('dechet_fitoura', 0)} kg"],
                ['Déchet Margin',
                    f"{traditional_metrics.get('dechet_margin', 0)} kg"],
                ['Prix par Litre',
                    f"{traditional_metrics.get('prix_litre', 0)} TND"],
                ['Coût Main d\'Œuvre',
                    f"{traditional_metrics.get('cout_main_oeuvre', 0)} TND"],
                ['Coût Eau', f"{traditional_metrics.get('cout_eau', 0)} TND"],
                ['Coût Énergétique',
                    f"{traditional_metrics.get('cout_energetique', 0)} TND"],
                ['Coût Total',
                    f"{traditional_metrics.get('cout_total', 0)} TND"]
            ]

            traditional_table = Table(traditional_data, colWidths=[7*cm, 4*cm])
            traditional_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkslateblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 1), (-1, -1), colors.thistle),
            ]))

            story.append(traditional_table)
            story.append(Spacer(1, 30))

        # Mapping Information Section
        if 'mapping_info' in predictions:
            story.append(Paragraph("Informations de Mappage ML", subtitle_style))
            mapping = predictions['mapping_info']
            mapping_data = [
                ['Entrée Originale', 'Mappage ML'],
                ['Région Source', mapping.get('source_region', 'N/A')],
                ['Type d\'Olive', mapping.get('olive_type_ml', 'N/A')],
                ['Méthode de Pression', mapping.get('press_method', 'N/A')],
                ['Condition', mapping.get('condition', 'N/A')],
                ['Taille d\'Olive', mapping.get('olive_size', 'N/A')],
                ['Quantité (tonnes)', str(mapping.get('quantity_tons_input', 0))]
            ]

            mapping_table = Table(mapping_data, colWidths=[7*cm, 4*cm])
            mapping_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.purple),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lavender),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(mapping_table)
            story.append(Spacer(1, 30))

        # Summary section
        if charts_created > 0:
            story.append(Paragraph("Résumé de l'Analyse", subtitle_style))
            summary_text = f"""
            Ce rapport présente une analyse complète du produit #{product.id} incluant:
            
            • {charts_created} graphiques d'analyse visuelle
            • Prédictions ML avancées pour les coûts et la production
            • Comparaison avec les méthodes traditionnelles
            • Répartition détaillée des déchets et des coûts
            
            Les prédictions sont basées sur des modèles d'apprentissage automatique 
            entraînés sur des données historiques de production d'huile d'olive.
            """
            story.append(Paragraph(summary_text, styles['Normal']))
            story.append(Spacer(1, 20))

        # Model Performance Info (if available)
        if global_prediction_service.model_info:
            story.append(Paragraph("Performance du Modèle ML", subtitle_style))
            model_info = global_prediction_service.model_info
            
            performance_data = [
                ['Métrique de Performance', 'Valeur'],
                ['R² Score (Coûts)', f"{model_info.get('cost_r2_score', 0):.3f}"],
                ['R² Score (Production)', f"{model_info.get('production_r2_score', 0):.3f}"],
                ['Nombre d\'échantillons d\'entraînement', str(model_info.get('training_samples', 'N/A'))],
                ['Date du modèle', model_info.get('model_date', 'N/A')]
            ]
            
            performance_table = Table(performance_data, colWidths=[7*cm, 4*cm])
            performance_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.teal),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightcyan),
            ]))
            story.append(performance_table)
            story.append(Spacer(1, 20))

        # Footer
        story.append(Paragraph(
            "Rapport généré par le Service de Prédiction ML Avancé", styles['Normal']))
        story.append(Paragraph(
            f"Généré le: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
        story.append(
            Paragraph(f"Utilisateur: {request.user.username}", styles['Normal']))

        # Build PDF
        doc.build(story)
        return response

    except Exception as e:
        logger.error(f"Error generating enhanced prediction PDF: {e}")
        return Response({
            'error': f'Failed to generate enhanced prediction PDF: {str(e)}',
            'success': False
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Additional utility function for chart validation
def validate_chart_data(data, chart_type):
    """
    Validate data before chart creation to prevent errors
    """
    try:
        if chart_type == 'waste':
            fitoura, margin = data
            return fitoura > 0 or margin > 0

        elif chart_type == 'cost':
            costs = data
            return any(costs.get(key, 0) > 0 for key in ['electricity_cost_tnd', 'water_cost_tnd', 'labor_cost_tnd'])

        elif chart_type == 'comparison':
            product, predictions = data
            # Check if we have either ML data or traditional data for comparison
            has_ml_data = any([
                hasattr(
                    product, 'ml_predicted_energy_kwh') and product.ml_predicted_energy_kwh,
                hasattr(
                    product, 'ml_predicted_water_liters') and product.ml_predicted_water_liters,
                hasattr(
                    product, 'ml_predicted_employees') and product.ml_predicted_employees
            ])

            has_predictions = predictions and (
                'costs' in predictions or 'production' in predictions)

            return has_ml_data or has_predictions

        return False

    except Exception as e:
        logger.warning(f"Error validating chart data for {chart_type}: {e}")
        return False


# Enhanced error handling for matplotlib
def safe_matplotlib_operation(operation_func, *args, **kwargs):
    """
    Safely execute matplotlib operations with proper cleanup
    """
    try:
        return operation_func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Matplotlib operation failed: {e}")
        plt.close('all')  # Clean up any open figures
        return None
    finally:
        # Ensure memory cleanup
        plt.clf()
        plt.cla()

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def prediction_metrics(request):
    """
    Get enhanced prediction service metrics and statistics
    """
    try:
        if not hasattr(request.user, 'role') or request.user.role not in ['ADMIN', 'EMPLOYEE']:
            return Response({
                'error': 'Only admins and employees can access prediction metrics',
                'success': False
            }, status=status.HTTP_403_FORBIDDEN)

        # Basic service metrics
        metrics = {
            'service_info': {
                'is_loaded': global_prediction_service.is_loaded,
                'service_type': 'Enhanced ML Prediction Service',
                'version': '2.0.0'
            },
            'model_info': global_prediction_service.get_model_status(),
            'data_statistics': {},
            'usage_statistics': {},
            'timestamp': timezone.now()
        }

        # Data statistics from products
        try:
            total_products = Product.objects.count()
            ml_products = Product.objects.filter(
                ml_prediction_generated=True).count()

            # Quality distribution
            quality_dist = Product.objects.values(
                'quality').annotate(count=Count('id'))
            quality_stats = {item['quality']: item['count']
                             for item in quality_dist}

            # Source distribution
            source_dist = Product.objects.exclude(source__isnull=True).exclude(
                source__exact='').values('source').annotate(count=Count('id'))[:10]
            source_stats = {item['source']: item['count']
                            for item in source_dist}

            metrics['data_statistics'] = {
                'total_products': total_products,
                'products_with_ml': ml_products,
                'ml_coverage_percentage': round((ml_products / total_products * 100), 2) if total_products > 0 else 0,
                'quality_distribution': quality_stats,
                'top_sources': source_stats
            }

            # ML prediction statistics
            if ml_products > 0:
                ml_stats = Product.objects.filter(ml_prediction_generated=True).aggregate(
                    avg_energy=Avg('ml_predicted_energy_kwh'),
                    total_energy=Sum('ml_predicted_energy_kwh'),
                    avg_water=Avg('ml_predicted_water_liters'),
                    total_water=Sum('ml_predicted_water_liters'),
                    avg_employees=Avg('ml_predicted_employees'),
                    total_employees=Sum('ml_predicted_employees')
                )

                metrics['ml_statistics'] = {
                    'averages': {
                        'energy_kwh': float(ml_stats['avg_energy'] or 0),
                        'water_liters': float(ml_stats['avg_water'] or 0),
                        'employees': float(ml_stats['avg_employees'] or 0)
                    },
                    'totals': {
                        'energy_kwh': float(ml_stats['total_energy'] or 0),
                        'water_liters': float(ml_stats['total_water'] or 0),
                        'employees': int(ml_stats['total_employees'] or 0)
                    }
                }

        except Exception as e:
            logger.warning(f"Error getting data statistics: {e}")
            metrics['data_statistics'] = {'error': str(e)}

        # Cache usage (simplified)
        try:
            cache.set('metrics_test', 'test', timeout=60)
            cache_test = cache.get('metrics_test')
            cache.delete('metrics_test')

            metrics['cache_statistics'] = {
                'backend': cache.__class__.__name__,
                'test_successful': cache_test == 'test',
                'estimated_keys': 'N/A'
            }
        except Exception as e:
            metrics['cache_statistics'] = {'error': str(e)}

        return Response(metrics, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error getting prediction metrics: {e}")
        return Response({
            'error': f'Failed to get prediction metrics: {str(e)}',
            'success': False
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def batch_prediction(request):
    """
    Perform batch predictions for multiple scenarios using enhanced ML service
    """
    try:
        data = request.data
        scenarios = data.get('scenarios', [])
        prediction_type = data.get('prediction_type', 'all')

        if not scenarios:
            return Response({
                'error': 'No scenarios provided',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)

        if len(scenarios) > 50:  # Limit batch size
            return Response({
                'error': 'Maximum 50 scenarios allowed per batch',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate scenarios format
        for i, scenario in enumerate(scenarios):
            required_fields = ['quantities']
            for field in required_fields:
                if field not in scenario:
                    return Response({
                        'error': f'Scenario {i+1} missing required field: {field}',
                        'success': False
                    }, status=status.HTTP_400_BAD_REQUEST)

        # Process batch predictions
        batch_results = {
            'total_scenarios': len(scenarios),
            'prediction_type': prediction_type,
            'results': [],
            'summary': {},
            'timestamp': timezone.now(),
            'success': True
        }

        for i, scenario in enumerate(scenarios):
            try:
                quantities = scenario.get('quantities', [])
                if isinstance(quantities, str):
                    quantities = [float(q.strip())
                                  for q in quantities.split(',')]

                # Perform prediction based on type
                if prediction_type == 'energy':
                    result = global_prediction_service.predict_energy_consumption(
                        quantities_range=quantities)
                elif prediction_type == 'water':
                    result = global_prediction_service.predict_water_consumption(
                        quantities_range=quantities)
                elif prediction_type == 'employees':
                    result = global_prediction_service.predict_employee_requirements(
                        quantities_range=quantities)
                elif prediction_type == 'quality':
                    result = global_prediction_service.predict_quality(
                        quantities_range=quantities)
                else:  # 'all' or default
                    result = global_prediction_service.predict_all_targets(
                        quantities_range=quantities)

                batch_results['results'].append({
                    'scenario_id': i + 1,
                    'input': scenario,
                    'prediction': result,
                    'success': result.get('success', False)
                })

            except Exception as e:
                batch_results['results'].append({
                    'scenario_id': i + 1,
                    'input': scenario,
                    'error': str(e),
                    'success': False
                })

        successful_results = [
            r for r in batch_results['results'] if r['success']]
        batch_results['summary'] = {
            'successful_predictions': len(successful_results),
            'failed_predictions': len(scenarios) - len(successful_results),
            'success_rate': round((len(successful_results) / len(scenarios) * 100), 2)
        }

        return Response(batch_results, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error in batch prediction: {e}")
        return Response({
            'error': f'Failed to process batch predictions: {str(e)}',
            'success': False
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
