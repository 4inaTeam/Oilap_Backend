# predict/views.py

from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import permissions, status
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from django.db.models.functions import Extract
from decimal import Decimal
import logging
import json
import hashlib

from .ml_service import global_prediction_service
from products.models import Product

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
                if predictions['main_targets']:
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
                'predict_energy_',
                'predict_water_',
                'predict_employees_',
                'predict_all_',
                'predict_quality_',
                'seasonal_analysis'
            ]

            for pattern in cache_patterns:
                # In production, you'd want more sophisticated cache key management
                # This is a simplified approach
                if pattern == 'seasonal_analysis':
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
        global_prediction_service.__init__()

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
            'service': 'ML Prediction API',
            'status': 'healthy' if global_prediction_service.is_loaded else 'unhealthy',
            'timestamp': timezone.now(),
            'version': '1.0.0',
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
            'service': 'ML Prediction API',
            'status': 'error',
            'timestamp': timezone.now(),
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def prediction_metrics(request):
    """
    Get prediction service metrics and statistics
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
                'uptime': 'N/A',  # Would need startup tracking for real uptime
                'version': '1.0.0'
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
                # Top 10 sources
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
    Perform batch predictions for multiple scenarios
    """
    try:
        data = request.data
        scenarios = data.get('scenarios', [])
        # all, energy, water, employees, quality
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
