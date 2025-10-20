# tests/test_distance_failures.py
import unittest
import distance_unary_pb2 as pb2
from distance_grpc_service import DistanceServicer
from geo_location import Position
import geopy.distance


class TestDistanceFailureCases(unittest.TestCase):
    """Casos de prueba diseñados para provocar fallos y verificar el manejo de errores."""

    def setUp(self):
        self.serv = DistanceServicer()

    # --- 1. Pruebas de valores fuera de rango ---

    def test_latitude_below_minimum(self):
        """Latitud < -90 debería lanzar ValueError (rango inválido)."""
        with self.assertRaises(ValueError):
            Position(-91.0, 0.0, 0.0)

    def test_latitude_above_maximum(self):
        """Latitud > 90 debería lanzar ValueError."""
        with self.assertRaises(ValueError):
            Position(91.0, 0.0, 0.0)

    def test_longitude_below_minimum(self):
        """Longitud < -180 debería lanzar ValueError."""
        with self.assertRaises(ValueError):
            Position(0.0, -181.0, 0.0)

    def test_longitude_above_maximum(self):
        """Longitud > 180 debería lanzar ValueError."""
        with self.assertRaises(ValueError):
            Position(0.0, 181.0, 0.0)

    # --- 2. Pruebas con datos malformados ---

    def test_latitude_as_string(self):
        """Si latitud se pasa como string, debe lanzar TypeError o ValueError."""
        with self.assertRaises((TypeError, ValueError)):
            Position("34.5", 40.0, 0.0)

    def test_longitude_none_value(self):
        """Si longitud es None, el sistema debe fallar."""
        with self.assertRaises((TypeError, ValueError)):
            Position(30.0, None, 0.0)

    # --- 3. Pruebas de servicio con entradas inválidas ---

    def test_service_invalid_latitude_source(self):
        """Latitud de origen inválida debe devolver distance=-1.0 y unit='invalid'."""
        req = pb2.SourceDest(
            source=pb2.Position(latitude=-100.0, longitude=10.0, altitude=0.0),
            destination=pb2.Position(latitude=0.0, longitude=10.0, altitude=0.0),
            unit="km",
        )
        resp = self.serv.geodesic_distance(req, None)
        self.assertEqual(resp.distance, -1.0)
        self.assertEqual(resp.unit, "invalid")

    def test_service_invalid_longitude_destination(self):
        """Longitud de destino inválida debe devolver distance=-1.0."""
        req = pb2.SourceDest(
            source=pb2.Position(latitude=0.0, longitude=10.0, altitude=0.0),
            destination=pb2.Position(latitude=0.0, longitude=999.0, altitude=0.0),
            unit="km",
        )
        resp = self.serv.geodesic_distance(req, None)
        self.assertEqual(resp.distance, -1.0)
        self.assertEqual(resp.unit, "invalid")

    def test_service_unit_unexpected_value(self):
        """Unidad desconocida debe devolver -1.0 y 'invalid' o lanzar excepción."""
        req = pb2.SourceDest(
            source=pb2.Position(latitude=10.0, longitude=20.0, altitude=0.0),
            destination=pb2.Position(latitude=30.0, longitude=40.0, altitude=0.0),
            unit="lightyears",  # unidad inexistente
        )
        with self.assertRaises(Exception):
            self.serv.geodesic_distance(req, None)

    # --- 4. Prueba del fallo en unidad vacía (requisito principal) ---

    def test_service_empty_unit_should_return_kilometers(self):
        """
        Si la unidad esperada está en blanco, la respuesta debe ser en kilómetros.
        Este test verifica que la distancia devuelta sea correcta (en km) y detecta
        el fallo de cálculo actual (usa .nautical() en vez de .km()).
        """
        req = pb2.SourceDest(
            source=pb2.Position(latitude=-33.0351516, longitude=-70.5955963, altitude=0.0),
            destination=pb2.Position(latitude=-33.0348327, longitude=-71.5980458, altitude=0.0),
            unit="",  # unidad vacía (por defecto debería ser km)
        )
        resp = self.serv.geodesic_distance(req, None)

        expected_km = geopy.distance.geodesic(
            (-33.0351516, -70.5955963), (-33.0348327, -71.5980458)
        ).km

        # Imprime los valores para evidencia en el informe
        print("\n[INFO] Distancia esperada (km):", expected_km)
        print("[INFO] Distancia devuelta por el servicio:", resp.distance)
        print("[INFO] Unidad reportada:", resp.unit)

        # Prueba de validación
        self.assertEqual(resp.unit, "km")
        # Esto fallará si la distancia no está en km (bug actual)
        self.assertAlmostEqual(resp.distance, expected_km, delta=0.5)

    # --- 5. Pruebas de valores frontera extremos ---

    def test_latitude_exact_boundary(self):
        """Latitudes exactas de frontera (-90, 90) deben ser válidas."""
        Position(-90.0, 0.0, 0.0)
        Position(90.0, 0.0, 0.0)

    def test_longitude_exact_boundary(self):
        """Longitudes exactas de frontera (-180, 180) deben ser válidas."""
        Position(0.0, -180.0, 0.0)
        Position(0.0, 180.0, 0.0)

    # --- 6. Pruebas de entradas incompletas ---

    def test_missing_destination_position(self):
        """Falta el destino -> debería generar error."""
        req = pb2.SourceDest(
            source=pb2.Position(latitude=0.0, longitude=0.0, altitude=0.0)
        )
        with self.assertRaises(Exception):
            self.serv.geodesic_distance(req, None)

    def test_missing_source_position(self):
        """Falta el origen -> debería generar error."""
        req = pb2.SourceDest(
            destination=pb2.Position(latitude=0.0, longitude=0.0, altitude=0.0)
        )
        with self.assertRaises(Exception):
            self.serv.geodesic_distance(req, None)

if __name__ == "__main__":
    unittest.main()

    def test_service_nautical_miles_calculation(self):
        """
        Verifica que unit='nm' devuelva una distancia correcta en millas náuticas.
        Si el servicio usa un factor de conversión incorrecto (1 nm = 1.852 km),
        este test lo detectará.
        """
        req = pb2.SourceDest(
            source=pb2.Position(latitude=-33.0351516, longitude=-70.5955963, altitude=0.0),
            destination=pb2.Position(latitude=-33.0348327, longitude=-71.5980458, altitude=0.0),
            unit="nm",  # prueba con millas náuticas
        )
        resp = self.serv.geodesic_distance(req, None)

        # cálculo esperado con geopy (kilómetros convertidos a nm)
        expected_km = geopy.distance.geodesic(
            (-33.0351516, -70.5955963), (-33.0348327, -71.5980458)
        ).km
        expected_nm = expected_km / 1.852

        print("\n[INFO] Distancia esperada (nm):", expected_nm)
        print("[INFO] Distancia devuelta por el servicio:", resp.distance)

        # Comparaciones
        self.assertEqual(resp.unit, "nm")
        # Esto fallará si el cálculo del servicio no usa correctamente el factor 1.852
        self.assertAlmostEqual(resp.distance, expected_nm, delta=0.5)
