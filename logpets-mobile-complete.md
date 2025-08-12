# LogPets PRO - Mobile App Flutter Completo
# GPS Tracking + Offline Support + Real-time Updates

## pubspec.yaml
```yaml
name: logpets_pro_mobile
description: Sistema completo de gestão de transporte de animais - App Mobile

publish_to: 'none'

version: 1.0.0+1

environment:
  sdk: '>=3.0.0 <4.0.0'
  flutter: ">=3.10.0"

dependencies:
  flutter:
    sdk: flutter
  cupertino_icons: ^1.0.2
  
  # State Management
  provider: ^6.1.1
  flutter_riverpod: ^2.4.9
  
  # HTTP & API
  http: ^1.1.0
  dio: ^5.3.2
  
  # Local Storage
  shared_preferences: ^2.2.2
  sqflite: ^2.3.0
  
  # GPS & Location
  geolocator: ^10.1.0
  location: ^5.0.3
  google_maps_flutter: ^2.5.0
  
  # Permissions
  permission_handler: ^11.0.1
  
  # Background Tasks
  workmanager: ^0.5.2
  
  # JSON Serialization
  json_annotation: ^4.8.1
  
  # Date & Time
  intl: ^0.19.0
  
  # Utilities
  path_provider: ^2.1.1
  uuid: ^4.1.0
  
  # UI Components
  flutter_svg: ^2.0.9
  cached_network_image: ^3.3.0
  lottie: ^2.7.0
  
  # Forms & Validation
  flutter_form_builder: ^9.1.1
  form_builder_validators: ^9.1.0

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^3.0.0
  build_runner: ^2.4.7
  json_serializable: ^6.7.1

flutter:
  uses-material-design: true
  assets:
    - assets/images/
    - assets/icons/
    - assets/animations/

flutter_icons:
  android: "launcher_icon"
  ios: true
  image_path: "assets/icons/app_icon.png"
```

## lib/main.dart
```dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:geolocator/geolocator.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:workmanager/workmanager.dart';

import 'app.dart';
import 'providers/auth_provider.dart';
import 'providers/trip_provider.dart';
import 'providers/gps_provider.dart';
import 'providers/vehicle_provider.dart';
import 'services/api_service.dart';
import 'services/gps_service.dart';
import 'services/offline_service.dart';
import 'config/app_config.dart';

@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((task, inputData) async {
    switch (task) {
      case 'gps_tracking':
        await GPSService.backgroundLocationUpdate();
        break;
      case 'sync_offline_data':
        await OfflineService.syncOfflineData();
        break;
    }
    return Future.value(true);
  });
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Configurar orientação
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);
  
  // Inicializar WorkManager para tarefas em background
  await Workmanager().initialize(callbackDispatcher, isInDebugMode: false);
  
  // Solicitar permissões
  await _requestPermissions();
  
  // Inicializar serviços
  await _initializeServices();
  
  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider(create: (_) => TripProvider()),
        ChangeNotifierProvider(create: (_) => GPSProvider()),
        ChangeNotifierProvider(create: (_) => VehicleProvider()),
      ],
      child: LogPetsApp(),
    ),
  );
}

Future<void> _requestPermissions() async {
  // Permissões de localização
  await Permission.location.request();
  await Permission.locationAlways.request();
  await Permission.locationWhenInUse.request();
  
  // Permissões de armazenamento
  await Permission.storage.request();
  
  // Permissões de câmera (para fotos de documentos)
  await Permission.camera.request();
}

Future<void> _initializeServices() async {
  await APIService.initialize();
  await OfflineService.initialize();
  await GPSService.initialize();
}
```

## lib/app.dart
```dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'screens/splash/splash_screen.dart';
import 'screens/auth/login_screen.dart';
import 'screens/auth/register_screen.dart';
import 'screens/home/home_screen.dart';
import 'screens/trips/trip_list_screen.dart';
import 'screens/trips/trip_tracking_screen.dart';
import 'screens/trips/trip_form_screen.dart';
import 'screens/vehicles/vehicle_list_screen.dart';
import 'screens/vehicles/vehicle_form_screen.dart';
import 'providers/auth_provider.dart';
import 'config/app_theme.dart';

class LogPetsApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'LogPets PRO',
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: ThemeMode.system,
      debugShowCheckedModeBanner: false,
      home: Consumer<AuthProvider>(
        builder: (context, auth, child) {
          if (auth.isLoading) {
            return SplashScreen();
          }
          
          return auth.isAuthenticated ? HomeScreen() : LoginScreen();
        },
      ),
      routes: {
        '/login': (context) => LoginScreen(),
        '/register': (context) => RegisterScreen(),
        '/home': (context) => HomeScreen(),
        '/trips': (context) => TripListScreen(),
        '/trips/new': (context) => TripFormScreen(),
        '/trips/tracking': (context) => TripTrackingScreen(),
        '/vehicles': (context) => VehicleListScreen(),
        '/vehicles/new': (context) => VehicleFormScreen(),
      },
    );
  }
}
```

## lib/services/gps_service.dart
```dart
import 'dart:async';
import 'dart:convert';
import 'package:geolocator/geolocator.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/gps_location.dart';
import '../services/api_service.dart';
import '../services/offline_service.dart';

class GPSService {
  static StreamSubscription<Position>? _positionStream;
  static bool _isTracking = false;
  static int? _currentTripId;
  
  static Future<void> initialize() async {
    await _checkPermissions();
  }
  
  static Future<bool> _checkPermissions() async {
    bool serviceEnabled;
    LocationPermission permission;

    serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      return false;
    }

    permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) {
        return false;
      }
    }
    
    if (permission == LocationPermission.deniedForever) {
      return false;
    }

    return true;
  }
  
  static Future<Position?> getCurrentLocation() async {
    try {
      if (!await _checkPermissions()) {
        return null;
      }
      
      return await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );
    } catch (e) {
      print('Erro ao obter localização: $e');
      return null;
    }
  }
  
  static Future<void> startTracking(int tripId) async {
    if (_isTracking) {
      await stopTracking();
    }
    
    _currentTripId = tripId;
    _isTracking = true;
    
    // Salvar estado de tracking
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('is_tracking', true);
    await prefs.setInt('current_trip_id', tripId);
    
    const LocationSettings locationSettings = LocationSettings(
      accuracy: LocationAccuracy.high,
      distanceFilter: 10, // Atualizar a cada 10 metros
    );
    
    _positionStream = Geolocator.getPositionStream(
      locationSettings: locationSettings,
    ).listen(
      (Position position) {
        _handleLocationUpdate(position);
      },
      onError: (error) {
        print('Erro no GPS tracking: $error');
      },
    );
  }
  
  static Future<void> stopTracking() async {
    _isTracking = false;
    _currentTripId = null;
    
    await _positionStream?.cancel();
    _positionStream = null;
    
    // Limpar estado de tracking
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('is_tracking');
    await prefs.remove('current_trip_id');
  }
  
  static Future<void> _handleLocationUpdate(Position position) async {
    if (!_isTracking || _currentTripId == null) return;
    
    final gpsLocation = GPSLocation(
      tripId: _currentTripId!,
      latitude: position.latitude,
      longitude: position.longitude,
      speed: position.speed,
      timestamp: DateTime.now(),
    );
    
    try {
      // Tentar enviar para o servidor
      await APIService.saveGPSLocation(gpsLocation);
    } catch (e) {
      // Se falhar, salvar offline
      await OfflineService.saveGPSLocationOffline(gpsLocation);
    }
  }
  
  static Future<void> backgroundLocationUpdate() async {
    final prefs = await SharedPreferences.getInstance();
    final isTracking = prefs.getBool('is_tracking') ?? false;
    final tripId = prefs.getInt('current_trip_id');
    
    if (!isTracking || tripId == null) return;
    
    final position = await getCurrentLocation();
    if (position != null) {
      final gpsLocation = GPSLocation(
        tripId: tripId,
        latitude: position.latitude,
        longitude: position.longitude,
        speed: position.speed,
        timestamp: DateTime.now(),
      );
      
      try {
        await APIService.saveGPSLocation(gpsLocation);
      } catch (e) {
        await OfflineService.saveGPSLocationOffline(gpsLocation);
      }
    }
  }
  
  static bool get isTracking => _isTracking;
  static int? get currentTripId => _currentTripId;
}
```

## lib/services/offline_service.dart
```dart
import 'dart:convert';
import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';
import '../models/trip.dart';
import '../models/vehicle.dart';
import '../models/gps_location.dart';
import '../services/api_service.dart';

class OfflineService {
  static Database? _database;
  
  static Future<void> initialize() async {
    await _initDatabase();
  }
  
  static Future<void> _initDatabase() async {
    final dbPath = await getDatabasesPath();
    final path = join(dbPath, 'logpets_offline.db');
    
    _database = await openDatabase(
      path,
      version: 1,
      onCreate: (db, version) async {
        // Tabela para viagens offline
        await db.execute('''
          CREATE TABLE offline_trips(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER,
            origin TEXT,
            destination TEXT,
            start_date TEXT,
            start_km REAL,
            trip_value REAL,
            data TEXT,
            sync_status INTEGER DEFAULT 0
          )
        ''');
        
        // Tabela para localizações GPS offline
        await db.execute('''
          CREATE TABLE offline_gps_locations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER,
            latitude REAL,
            longitude REAL,
            speed REAL,
            timestamp TEXT,
            sync_status INTEGER DEFAULT 0
          )
        ''');
        
        // Tabela para veículos (cache)
        await db.execute('''
          CREATE TABLE cached_vehicles(
            id INTEGER PRIMARY KEY,
            license_plate TEXT,
            model TEXT,
            year INTEGER,
            data TEXT,
            last_updated TEXT
          )
        ''');
      },
    );
  }
  
  static Future<void> saveTripOffline(Trip trip) async {
    if (_database == null) await _initDatabase();
    
    await _database!.insert(
      'offline_trips',
      {
        'vehicle_id': trip.vehicleId,
        'origin': trip.origin,
        'destination': trip.destination,
        'start_date': trip.startDate.toIso8601String(),
        'start_km': trip.startKm,
        'trip_value': trip.tripValue,
        'data': jsonEncode(trip.toJson()),
        'sync_status': 0,
      },
    );
  }
  
  static Future<void> saveGPSLocationOffline(GPSLocation location) async {
    if (_database == null) await _initDatabase();
    
    await _database!.insert(
      'offline_gps_locations',
      {
        'trip_id': location.tripId,
        'latitude': location.latitude,
        'longitude': location.longitude,
        'speed': location.speed,
        'timestamp': location.timestamp.toIso8601String(),
        'sync_status': 0,
      },
    );
  }
  
  static Future<void> cacheVehicles(List<Vehicle> vehicles) async {
    if (_database == null) await _initDatabase();
    
    final batch = _database!.batch();
    
    // Limpar cache anterior
    batch.delete('cached_vehicles');
    
    // Inserir novos dados
    for (final vehicle in vehicles) {
      batch.insert('cached_vehicles', {
        'id': vehicle.id,
        'license_plate': vehicle.licensePlate,
        'model': vehicle.model,
        'year': vehicle.year,
        'data': jsonEncode(vehicle.toJson()),
        'last_updated': DateTime.now().toIso8601String(),
      });
    }
    
    await batch.commit();
  }
  
  static Future<List<Vehicle>> getCachedVehicles() async {
    if (_database == null) await _initDatabase();
    
    final result = await _database!.query('cached_vehicles');
    
    return result.map((row) {
      final data = jsonDecode(row['data'] as String);
      return Vehicle.fromJson(data);
    }).toList();
  }
  
  static Future<void> syncOfflineData() async {
    await _syncOfflineTrips();
    await _syncOfflineGPSLocations();
  }
  
  static Future<void> _syncOfflineTrips() async {
    if (_database == null) await _initDatabase();
    
    final result = await _database!.query(
      'offline_trips',
      where: 'sync_status = ?',
      whereArgs: [0],
    );
    
    for (final row in result) {
      try {
        final data = jsonDecode(row['data'] as String);
        final trip = Trip.fromJson(data);
        
        await APIService.createTrip(trip);
        
        // Marcar como sincronizado
        await _database!.update(
          'offline_trips',
          {'sync_status': 1},
          where: 'id = ?',
          whereArgs: [row['id']],
        );
      } catch (e) {
        print('Erro ao sincronizar viagem offline: $e');
      }
    }
  }
  
  static Future<void> _syncOfflineGPSLocations() async {
    if (_database == null) await _initDatabase();
    
    final result = await _database!.query(
      'offline_gps_locations',
      where: 'sync_status = ?',
      whereArgs: [0],
    );
    
    for (final row in result) {
      try {
        final location = GPSLocation(
          tripId: row['trip_id'] as int,
          latitude: row['latitude'] as double,
          longitude: row['longitude'] as double,
          speed: row['speed'] as double?,
          timestamp: DateTime.parse(row['timestamp'] as String),
        );
        
        await APIService.saveGPSLocation(location);
        
        // Marcar como sincronizado
        await _database!.update(
          'offline_gps_locations',
          {'sync_status': 1},
          where: 'id = ?',
          whereArgs: [row['id']],
        );
      } catch (e) {
        print('Erro ao sincronizar localização GPS offline: $e');
      }
    }
  }
  
  static Future<bool> hasOfflineData() async {
    if (_database == null) await _initDatabase();
    
    final tripCount = Sqflite.firstIntValue(
      await _database!.rawQuery(
        'SELECT COUNT(*) FROM offline_trips WHERE sync_status = 0'
      )
    ) ?? 0;
    
    final locationCount = Sqflite.firstIntValue(
      await _database!.rawQuery(
        'SELECT COUNT(*) FROM offline_gps_locations WHERE sync_status = 0'
      )
    ) ?? 0;
    
    return tripCount > 0 || locationCount > 0;
  }
}
```

## lib/models/trip.dart
```dart
import 'package:json_annotation/json_annotation.dart';

part 'trip.g.dart';

@JsonSerializable()
class Trip {
  final int? id;
  @JsonKey(name: 'vehicle_id')
  final int vehicleId;
  @JsonKey(name: 'driver_id')
  final int? driverId;
  final String origin;
  final String destination;
  @JsonKey(name: 'start_date')
  final DateTime startDate;
  @JsonKey(name: 'end_date')
  final DateTime? endDate;
  @JsonKey(name: 'start_km')
  final double startKm;
  @JsonKey(name: 'end_km')
  final double? endKm;
  @JsonKey(name: 'total_km')
  final double? totalKm;
  @JsonKey(name: 'trip_value')
  final double? tripValue;
  @JsonKey(name: 'fuel_cost')
  final double? fuelCost;
  @JsonKey(name: 'toll_cost')
  final double? tollCost;
  @JsonKey(name: 'extra_costs')
  final double? extraCosts;
  @JsonKey(name: 'total_cost')
  final double? totalCost;
  final double? profit;
  @JsonKey(name: 'profit_margin')
  final double? profitMargin;
  final String? status;
  @JsonKey(name: 'created_at')
  final DateTime? createdAt;

  Trip({
    this.id,
    required this.vehicleId,
    this.driverId,
    required this.origin,
    required this.destination,
    required this.startDate,
    this.endDate,
    required this.startKm,
    this.endKm,
    this.totalKm,
    this.tripValue,
    this.fuelCost,
    this.tollCost,
    this.extraCosts,
    this.totalCost,
    this.profit,
    this.profitMargin,
    this.status,
    this.createdAt,
  });

  factory Trip.fromJson(Map<String, dynamic> json) => _$TripFromJson(json);
  Map<String, dynamic> toJson() => _$TripToJson(this);
  
  Trip copyWith({
    int? id,
    int? vehicleId,
    int? driverId,
    String? origin,
    String? destination,
    DateTime? startDate,
    DateTime? endDate,
    double? startKm,
    double? endKm,
    double? totalKm,
    double? tripValue,
    double? fuelCost,
    double? tollCost,
    double? extraCosts,
    double? totalCost,
    double? profit,
    double? profitMargin,
    String? status,
    DateTime? createdAt,
  }) {
    return Trip(
      id: id ?? this.id,
      vehicleId: vehicleId ?? this.vehicleId,
      driverId: driverId ?? this.driverId,
      origin: origin ?? this.origin,
      destination: destination ?? this.destination,
      startDate: startDate ?? this.startDate,
      endDate: endDate ?? this.endDate,
      startKm: startKm ?? this.startKm,
      endKm: endKm ?? this.endKm,
      totalKm: totalKm ?? this.totalKm,
      tripValue: tripValue ?? this.tripValue,
      fuelCost: fuelCost ?? this.fuelCost,
      tollCost: tollCost ?? this.tollCost,
      extraCosts: extraCosts ?? this.extraCosts,
      totalCost: totalCost ?? this.totalCost,
      profit: profit ?? this.profit,
      profitMargin: profitMargin ?? this.profitMargin,
      status: status ?? this.status,
      createdAt: createdAt ?? this.createdAt,
    );
  }
}
```

## lib/widgets/maps/gps_map_widget.dart
```dart
import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:geolocator/geolocator.dart';
import '../../models/gps_location.dart';

class GPSMapWidget extends StatefulWidget {
  final List<GPSLocation> locations;
  final bool showCurrentLocation;
  final Function(LatLng)? onMapTap;

  const GPSMapWidget({
    Key? key,
    required this.locations,
    this.showCurrentLocation = true,
    this.onMapTap,
  }) : super(key: key);

  @override
  State<GPSMapWidget> createState() => _GPSMapWidgetState();
}

class _GPSMapWidgetState extends State<GPSMapWidget> {
  GoogleMapController? _controller;
  Position? _currentPosition;
  Set<Marker> _markers = {};
  Set<Polyline> _polylines = {};

  @override
  void initState() {
    super.initState();
    _getCurrentLocation();
    _updateMapData();
  }

  @override
  void didUpdateWidget(GPSMapWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.locations != widget.locations) {
      _updateMapData();
    }
  }

  Future<void> _getCurrentLocation() async {
    try {
      final position = await Geolocator.getCurrentPosition();
      setState(() {
        _currentPosition = position;
      });
    } catch (e) {
      print('Erro ao obter localização atual: $e');
    }
  }

  void _updateMapData() {
    final markers = <Marker>{};
    final polylinePoints = <LatLng>[];

    // Adicionar marcadores para cada localização
    for (int i = 0; i < widget.locations.length; i++) {
      final location = widget.locations[i];
      final position = LatLng(location.latitude, location.longitude);
      
      polylinePoints.add(position);
      
      // Marcador de início
      if (i == 0) {
        markers.add(
          Marker(
            markerId: MarkerId('start'),
            position: position,
            icon: BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueGreen),
            infoWindow: InfoWindow(
              title: 'Início',
              snippet: 'Velocidade: ${location.speed?.toStringAsFixed(1) ?? "N/A"} km/h',
            ),
          ),
        );
      }
      
      // Marcador de fim
      if (i == widget.locations.length - 1) {
        markers.add(
          Marker(
            markerId: MarkerId('end'),
            position: position,
            icon: BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueRed),
            infoWindow: InfoWindow(
              title: 'Fim',
              snippet: 'Velocidade: ${location.speed?.toStringAsFixed(1) ?? "N/A"} km/h',
            ),
          ),
        );
      }
    }

    // Adicionar localização atual se solicitado
    if (widget.showCurrentLocation && _currentPosition != null) {
      markers.add(
        Marker(
          markerId: MarkerId('current'),
          position: LatLng(_currentPosition!.latitude, _currentPosition!.longitude),
          icon: BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueBlue),
          infoWindow: InfoWindow(title: 'Localização Atual'),
        ),
      );
    }

    // Criar polilinha da rota
    if (polylinePoints.isNotEmpty) {
      _polylines = {
        Polyline(
          polylineId: PolylineId('route'),
          points: polylinePoints,
          color: Colors.blue,
          width: 4,
          patterns: [],
        ),
      };
    }

    setState(() {
      _markers = markers;
    });
  }

  @override
  Widget build(BuildContext context) {
    LatLng initialPosition = LatLng(-23.550520, -46.633309); // São Paulo como padrão
    
    if (_currentPosition != null) {
      initialPosition = LatLng(_currentPosition!.latitude, _currentPosition!.longitude);
    } else if (widget.locations.isNotEmpty) {
      final firstLocation = widget.locations.first;
      initialPosition = LatLng(firstLocation.latitude, firstLocation.longitude);
    }

    return GoogleMap(
      onMapCreated: (GoogleMapController controller) {
        _controller = controller;
        
        // Ajustar zoom para mostrar todas as localizações
        if (widget.locations.isNotEmpty) {
          _fitMapToLocations();
        }
      },
      initialCameraPosition: CameraPosition(
        target: initialPosition,
        zoom: 14.0,
      ),
      markers: _markers,
      polylines: _polylines,
      myLocationEnabled: widget.showCurrentLocation,
      myLocationButtonEnabled: true,
      zoomControlsEnabled: true,
      onTap: widget.onMapTap,
      mapType: MapType.normal,
    );
  }

  void _fitMapToLocations() {
    if (_controller == null || widget.locations.isEmpty) return;

    final bounds = _calculateBounds(widget.locations);
    
    _controller!.animateCamera(
      CameraUpdate.newLatLngBounds(bounds, 100.0),
    );
  }

  LatLngBounds _calculateBounds(List<GPSLocation> locations) {
    double minLat = locations.first.latitude;
    double maxLat = locations.first.latitude;
    double minLng = locations.first.longitude;
    double maxLng = locations.first.longitude;

    for (final location in locations) {
      minLat = minLat < location.latitude ? minLat : location.latitude;
      maxLat = maxLat > location.latitude ? maxLat : location.latitude;
      minLng = minLng < location.longitude ? minLng : location.longitude;
      maxLng = maxLng > location.longitude ? maxLng : location.longitude;
    }

    return LatLngBounds(
      southwest: LatLng(minLat, minLng),
      northeast: LatLng(maxLat, maxLng),
    );
  }
}
```

## android/app/src/main/AndroidManifest.xml
```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    
    <!-- Permissões de localização -->
    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
    <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
    <uses-permission android:name="android.permission.ACCESS_BACKGROUND_LOCATION" />
    
    <!-- Permissões de armazenamento -->
    <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" />
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" />
    
    <!-- Permissões de rede -->
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    
    <!-- Permissões de câmera -->
    <uses-permission android:name="android.permission.CAMERA" />
    
    <!-- Permissões para foreground service -->
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.WAKE_LOCK" />

    <application
        android:label="LogPets PRO"
        android:name="${applicationName}"
        android:icon="@mipmap/launcher_icon">
        
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:launchMode="singleTop"
            android:theme="@style/LaunchTheme"
            android:configChanges="orientation|keyboardHidden|keyboard|screenSize|smallestScreenSize|locale|layoutDirection|fontScale|screenLayout|density|uiMode"
            android:hardwareAccelerated="true"
            android:windowSoftInputMode="adjustResize">
            
            <meta-data
              android:name="io.flutter.embedding.android.NormalTheme"
              android:resource="@style/NormalTheme" />
              
            <intent-filter android:autoVerify="true">
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
        
        <!-- Google Maps API Key -->
        <meta-data 
            android:name="com.google.android.geo.API_KEY"
            android:value="YOUR_GOOGLE_MAPS_API_KEY"/>
            
        <!-- WorkManager -->
        <provider
            android:name="androidx.startup.InitializationProvider"
            android:authorities="${applicationId}.androidx-startup"
            android:exported="false"
            tools:node="merge">
            <meta-data
                android:name="androidx.work.WorkManagerInitializer"
                android:value="androidx.startup" />
        </provider>
        
        <meta-data
            android:name="flutterEmbedding"
            android:value="2" />
    </application>
    
    <!-- Queries para Android 11+ -->
    <queries>
        <intent>
            <action android:name="android.intent.action.VIEW" />
            <data android:scheme="https" />
        </intent>
    </queries>
</manifest>
```

## ios/Runner/Info.plist
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>$(DEVELOPMENT_LANGUAGE)</string>
    <key>CFBundleDisplayName</key>
    <string>LogPets PRO</string>
    <key>CFBundleExecutable</key>
    <string>$(EXECUTABLE_NAME)</string>
    <key>CFBundleIdentifier</key>
    <string>$(PRODUCT_BUNDLE_IDENTIFIER)</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>logpets_pro_mobile</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>$(FLUTTER_BUILD_NAME)</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>CFBundleVersion</key>
    <string>$(FLUTTER_BUILD_NUMBER)</string>
    <key>LSRequiresIPhoneOS</key>
    <true/>
    <key>UILaunchStoryboardName</key>
    <string>LaunchScreen</string>
    <key>UIMainStoryboardFile</key>
    <string>Main</string>
    <key>UISupportedInterfaceOrientations</key>
    <array>
        <string>UIInterfaceOrientationPortrait</string>
        <string>UIInterfaceOrientationPortraitUpsideDown</string>
    </array>
    <key>UISupportedInterfaceOrientations~ipad</key>
    <array>
        <string>UIInterfaceOrientationPortrait</string>
        <string>UIInterfaceOrientationPortraitUpsideDown</string>
        <string>UIInterfaceOrientationLandscapeLeft</string>
        <string>UIInterfaceOrientationLandscapeRight</string>
    </array>
    
    <!-- Permissões de localização -->
    <key>NSLocationWhenInUseUsageDescription</key>
    <string>O LogPets PRO precisa acessar sua localização para rastrear viagens</string>
    <key>NSLocationAlwaysAndWhenInUseUsageDescription</key>
    <string>O LogPets PRO precisa acessar sua localização em segundo plano para rastrear viagens</string>
    <key>NSLocationAlwaysUsageDescription</key>
    <string>O LogPets PRO precisa acessar sua localização em segundo plano para rastrear viagens</string>
    
    <!-- Permissões de câmera -->
    <key>NSCameraUsageDescription</key>
    <string>O LogPets PRO precisa acessar a câmera para fotografar documentos</string>
    
    <!-- Background modes -->
    <key>UIBackgroundModes</key>
    <array>
        <string>location</string>
        <string>background-fetch</string>
        <string>background-processing</string>
    </array>
    
    <key>UIViewControllerBasedStatusBarAppearance</key>
    <false/>
    
    <!-- Google Maps -->
    <key>io.flutter.embedded_views_preview</key>
    <true/>
</dict>
</plist>
```