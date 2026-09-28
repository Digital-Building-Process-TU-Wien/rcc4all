package com.solibri.rule;

import java.io.IOException;
import java.text.ParseException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.ExecutionException;

import com.solibri.geometry.linearalgebra.MVector2d;
import com.solibri.geometry.linearalgebra.Vector2d;
import com.solibri.geometry.linearalgebra.Vector3d;
import com.solibri.geometry.mesh.TriangleMesh;
import com.solibri.geometry.primitive2d.Area;
import com.solibri.geometry.primitive2d.MPolygon2d;
import com.solibri.geometry.primitive2d.Polygon2d;
import com.solibri.geometry.primitive3d.AABB3d;
import com.solibri.geometry.primitive3d.Polygon3d;
import com.solibri.smc.api.SMC;
import com.solibri.smc.api.checking.DoubleParameter;
import com.solibri.smc.api.checking.EnumerationParameter;
import com.solibri.smc.api.checking.FilterParameter;
import com.solibri.smc.api.checking.OneByOneRule;
import com.solibri.smc.api.checking.PreCheckResult;
import com.solibri.smc.api.checking.Result;
import com.solibri.smc.api.checking.ResultCategory;
import com.solibri.smc.api.checking.ResultFactory;
import com.solibri.smc.api.checking.RuleParameters;
import com.solibri.smc.api.checking.RuleResources;
import com.solibri.smc.api.checking.Severity;
import com.solibri.smc.api.filter.AABBIntersectionFilter;
import com.solibri.smc.api.filter.ComponentFilter;
import com.solibri.smc.api.ifc.IfcEntityType;
import com.solibri.smc.api.model.PropertyType;
import com.solibri.smc.api.model.Quantities;
import com.solibri.smc.api.model.Relation;
import com.solibri.smc.api.model.Quantities.Type;
import com.solibri.smc.api.model.components.Covering;
import com.solibri.smc.api.model.components.Door;
import com.solibri.smc.api.model.Component;
import com.solibri.smc.api.ui.BorderType;
import com.solibri.smc.api.ui.UIComponent;
import com.solibri.smc.api.ui.UIContainer;
import com.solibri.smc.api.ui.UIContainerHorizontal;
import com.solibri.smc.api.ui.UIContainerVertical;
import com.solibri.smc.api.ui.UIImage;
import com.solibri.smc.api.ui.UILabel;
import com.solibri.smc.api.ui.UIRadioButtonPanelHorizontal;
import com.solibri.smc.api.ui.UIRadioButtonPanelVertical;
import com.solibri.smc.api.ui.UIRuleParameter;
import com.solibri.smc.api.visualization.ARGBColor;
import com.solibri.smc.api.visualization.Mesh;

import service.Licence;
import service.LicencingResult;

public final class MovementAreaAtDoorsRule extends OneByOneRule{
	
	//Constant names - suggested by Solibri
	//Filterparamter
	private static final String COMPONENT_FILTER_OBSTACLES_ID = "rpComponentFilterObstacles";
	private static final String COMPONENT_FILTER_IRRELEVANT_SPACES_ID = "rpComponentFilterIrrelevantSpaces";
	//DoubleParameter
	private static final String CIRCLE_DIAMETER_PARAMETER_ID = "rpCircleDiameter";	
	private static final String RECTANGLE_SIDE_A_PARAMTER_ID ="rpRectangleSideA";
	private static final String RECTANGLE_SIDE_B_PARAMTER_ID ="rpRectangleSideB";
	private static final String AREA_OFFSET_PARAMETER_ID = "rpAreaOffset";
	private static final String OBJECT_HEIGHT_PARAMETER_ID = "rpObjectHeight";
	//EnumerationParameter
	private static final String CHOOSE_MOVEMENT_AREA_OBJECT_ID = "rpChooseMovementAreaObject";
	private static final String CHOOSE_CIRCLE_ID = "rpChooseCircle";
	private static final String CHOOSE_RECTANGLE_ID = "rpChooseRectangle";
	private static final String CHOOSE_OBJECT_HEIGHT_ID = "rpChooseObjectHeight";
	private static final String CHOOSE_DOOR_HEIGHT_ID = "rpChooseDoorHeight";
	private static final String CHOOSE_CUSTOM_HEIGHT_ID = "rpChooseCustomHeight";
					
	// Create the parameter creation handler for the rule
	private final RuleParameters params = RuleParameters.of(this);
	
	//Parameter for the user input
	//FilterParameter
	final FilterParameter rpComponentFilter = this.getDefaultFilterParameter();
	final FilterParameter rpComponentFilterObstacles = params.createFilter(COMPONENT_FILTER_OBSTACLES_ID);
	final FilterParameter rpComponentFilterIrrelevantSpaces = params.createFilter(COMPONENT_FILTER_IRRELEVANT_SPACES_ID);
	//DoubleParameter
	final DoubleParameter rpCircleDiameter = params.createDouble(CIRCLE_DIAMETER_PARAMETER_ID, PropertyType.LENGTH);
	final DoubleParameter rpRectangleSideA = params.createDouble(RECTANGLE_SIDE_A_PARAMTER_ID, PropertyType.LENGTH);
	final DoubleParameter rpRectangleSideB = params.createDouble(RECTANGLE_SIDE_B_PARAMTER_ID, PropertyType.LENGTH);
	final DoubleParameter rpAreaOffset = params.createDouble(AREA_OFFSET_PARAMETER_ID, PropertyType.LENGTH);
	final DoubleParameter rpObjectHeight = params.createDouble(OBJECT_HEIGHT_PARAMETER_ID, PropertyType.LENGTH);
	//EnumerationParameter
	private final EnumerationParameter rpEnumerationMovementArea = params.createEnumeration(CHOOSE_MOVEMENT_AREA_OBJECT_ID,
			Arrays.asList(CHOOSE_CIRCLE_ID, CHOOSE_RECTANGLE_ID));
	private final EnumerationParameter rpEnumerationObjectHeight = params.createEnumeration(CHOOSE_OBJECT_HEIGHT_ID,
			Arrays.asList(CHOOSE_DOOR_HEIGHT_ID, CHOOSE_CUSTOM_HEIGHT_ID));
		
	private final RuleResources resources = RuleResources.of(this);
		
	/* 
	 * Description
	 */
	
	private static final double toleranceGap = 0.01;
	
	@Override
	public PreCheckResult preCheck() {
		
		LicencingResult startRule;
		String name = SMC.getCurrentUser().getUsername();
		try {
			startRule = Licence.licenceMethod(name, this.getClass().getSimpleName());

			if (startRule.getStartRule() == true) {
				//Content of the precheck
				
				//check user input
				Collection<Component> obstacles = SMC.getModel().getComponents(rpComponentFilterObstacles.getValue());
				if(obstacles.isEmpty()) {
					return PreCheckResult.createIrrelevant(resources.getString("RE.MissingObstacles.NAME"));
				}
				
				if((rpEnumerationMovementArea.getValue().equals(CHOOSE_CIRCLE_ID) && rpCircleDiameter.getValue() <= 0)
						|| (rpEnumerationMovementArea.getValue().equals(CHOOSE_RECTANGLE_ID) && (rpRectangleSideA.getValue() <= 0 || rpRectangleSideB.getValue() <= 0))) {
					return PreCheckResult.createIrrelevant(resources.getString("RE.WrongDimensionValues.NAME"));
				}
				return PreCheckResult.createRelevant();
			} 
			//if no licence was found
			else {
				String irrelevant = startRule.getResultText();
				return PreCheckResult.createIrrelevant(irrelevant);
			}
		} catch (ParseException | IOException | InterruptedException | ExecutionException e) {
			return PreCheckResult.createIrrelevant("error");
		}
	}
	
	//Check method
	@Override
	public Collection<Result> check(Component component, ResultFactory resultFactory) {
		//Creating a collection of results that will be returned at the end of the check method
		Collection<Result> results = new ArrayList<>();
		//ResultCategories
		ResultCategory componentResult = resultFactory.createCategory(component.getName() + resources.getString("RC.ClashCategory.NAME"), component.getName() + resources.getString("RC.ClashCategory.NAME"));
		ResultCategory wrongInput = resultFactory.createCategory(resources.getString("RC.WrongInput.NAME"),resources.getString("RC.WrongInput.NAME"));
		
		//result if the given component is not from type door
		if(!(component instanceof Door)) {
			Result result = resultFactory.create(component.getName(), resources.getString("RE.WrongComponentType.DESCRIPTION"))
					.withCategory(wrongInput)
					.withSeverity(Severity.CRITICAL);
			return Collections.singleton(result);
		}
		Door door = (Door) component;
		
		//retrieve the related openings
		Collection<Component> relatedFillings = component.getRelated(Relation.of(Relation.Type.FILLS, Relation.Direction.BOTH));
		//result if no filling was found
		if(relatedFillings.isEmpty()) {
			Result result = resultFactory.create(component.getName(), resources.getString("RE.DoorWithoutWall.DESCRIPTION"))
					.withCategory(wrongInput)
					.withSeverity(Severity.CRITICAL);
			return Collections.singleton(result);
		}
		//getting the first and only opening out of the Collection
		Component doorOpening = relatedFillings.iterator().next();
		
		//Area of the Opening
		Area openingArea = doorOpening.getFootprint().getArea();
		//Centroid of the openingArea
		MVector2d openingAreaCentroid = openingArea.getCentroid();
		//Getting the thickness of the opening
		//First get the width from the quantities and then divide the area by the width
		Double openingWidth = Quantities.of(doorOpening).get(Type.WIDTH).get();
		Double openingAreaSize = openingArea.getSize();
		Double openingThickness = openingAreaSize/openingWidth;
		
		// Openingdirection of the door (elevator doors also have a referenceDirection perpendicular to the door)
		Vector3d doorOpeningDirection = door.getReferenceDirection();
		MVector2d doorOpeningDirection2d = doorOpeningDirection.to2dVector();
		
		//check the movement area in all nearest spaces (except irrelevantSpaces) of the current component
		Collection<Component> nearestSpaces = component.getRelated(Relation.of(Relation.Type.NEAREST_SPACES, Relation.Direction.FORWARD));
			
		//****************************************************
		//check the movement area at both sides of the door
		for(int i = 0; i < 2; i++) {
			Vector2d currentDirection = rotateVector(doorOpeningDirection2d, i*Math.PI);
			
			//Center of the movementArea
			MVector2d areaCenter = null;
			//Circle
			if(rpEnumerationMovementArea.getValue().equals(CHOOSE_CIRCLE_ID)) {
				// Defining the center of the circle
				areaCenter = openingAreaCentroid.add(currentDirection.scale((openingThickness/2 + rpAreaOffset.getValue() + rpCircleDiameter.getValue()/2)));
			}
			//Rectangle
			else if(rpEnumerationMovementArea.getValue().equals(CHOOSE_RECTANGLE_ID)) {
				// Defining the center of the rectangle
				areaCenter = openingAreaCentroid.add(currentDirection.scale((openingThickness/2 + rpAreaOffset.getValue() + rpRectangleSideB.getValue()/2)));
			}			
			
			//find the space at the current side of the door by checking whether a testpoint in front of the door is inside the space
			Component relatedSpace = null;
			MVector2d testPoint = openingAreaCentroid.add(currentDirection.scale((openingThickness/2 + 0.1)));
			for(Component nearestSpace : nearestSpaces) {
				//use all polygons of the space, because a space can be build from two separate polygons
				List<MPolygon2d> spacePolygons = nearestSpace.getFootprint().getArea().getPolygons();
				for(MPolygon2d spacePolygon : spacePolygons) {
					if(spacePolygon.contains(testPoint)) {
						relatedSpace = nearestSpace;
					}
				}
			}
			//if the related space is part of the irrelevant spaces, ignore it
			if(relatedSpace != null && rpComponentFilterIrrelevantSpaces.getValue().accept(relatedSpace)){
				continue;
			}
			
			//define the elevation of the movementArea
			//if no space is available in front of the door, the bottom elevation of the door is chosen
			double areaElevation = door.getGlobalBottomElevation();
			//otherwise the floor elevation of the space is determined
			if(relatedSpace != null) {
				areaElevation = defineFlooringElevation(relatedSpace, areaCenter, "top");
			}
			
			//Create a TriangleMesh for the shape of the movementArea
			TriangleMesh movementArea = null;
			double boundingBoxDiameter = 0;
			//topElevation dependent on user input
			double topElevation = 0;
			if(rpEnumerationObjectHeight.getValue().equals(CHOOSE_DOOR_HEIGHT_ID)) {
				topElevation = component.getGlobalTopElevation();
			}else {
				topElevation = areaElevation + rpObjectHeight.getValue();
			}
			//Cylinder
			if(rpEnumerationMovementArea.getValue().equals(CHOOSE_CIRCLE_ID)) {
				// Creating the vertices of the circle with an interval of 2 degrees
				//the diameter is decreased by the toleranceGap to avoid clashes when the required distance is given exactly 
				movementArea = createCylinderTriangleMesh(areaCenter, rpCircleDiameter.getValue() - toleranceGap, 72,
						areaElevation, topElevation);
				boundingBoxDiameter = 2*rpCircleDiameter.getValue();
			}
			//Cuboid
			else if(rpEnumerationMovementArea.getValue().equals(CHOOSE_RECTANGLE_ID)) {
				// Creating the vertices of the rectangle
				//the dimensions are decreased by the toleranceGap to avoid clashes when the required distance is given exactly 
				movementArea = createCuboidTriangleMesh(MVector2d.create(areaCenter), MVector2d.create(currentDirection),
						rpRectangleSideA.getValue() - toleranceGap, rpRectangleSideB.getValue() - toleranceGap,
						areaElevation, topElevation);
				boundingBoxDiameter = 2 * (rpRectangleSideA.getValue() + rpRectangleSideB.getValue());
			}
			
			// Getting the components of the target filter
			// Creating a BoundingBox in front of the Door for a precheck
			AABB3d customBoundingBox = createBoundingBox(areaCenter, areaElevation, component.getGlobalTopElevation(), boundingBoxDiameter);
			// Creating a filter that accepts the components of the filter which additionally intersect with the customBoundingBox 
			ComponentFilter targetComponentFilter = AABBIntersectionFilter.of(customBoundingBox).and(rpComponentFilterObstacles.getValue());
			// Storing the components of the targetComponentFilter in the collection targets
			Collection<Component> targets = SMC.getModel().getComponents(targetComponentFilter);
			
			// running the clashcheck-method for all target components
			for (Component target : targets) {
				//exclude BuildingElementParts, because they cause random StackOverflowErrors
				if(!target.getIfcEntityType().get().equals(IfcEntityType.IfcBuildingElementPart)) {
					results.addAll(clashCheck(component, target, areaElevation, movementArea, resultFactory, componentResult));
				}
			}
		}
		return results;
	} // End of the check-method (main-method)
	
	//************************************************************************************
	// rotateVector() rotates a given 2D-vector counterclockwise by the given angle
	// returns a new vector
	private MVector2d rotateVector (MVector2d inputVector, double angle) {
					
		double newX = inputVector.getX()*Math.cos(angle) - inputVector.getY()*Math.sin(angle);
		double newY = inputVector.getX()*Math.sin(angle) + inputVector.getY()*Math.cos(angle);
		
		MVector2d vector = MVector2d.create(newX, newY);
					
		return vector;
	}
	
	//************************************************************************************
	//defineFlooringElevation() calculates the elevation of the floor inside the given spaceComponent at the given point.
	//The String output defines whether the top or bottom elevation of the floor object should be returned
	private double defineFlooringElevation(Component spaceComponent, Vector2d point, String output) {
		// set elevation of the space as default if no flooring is available
		double topElevation = spaceComponent.getGlobalBottomElevation();
		double bottomElevation = spaceComponent.getGlobalBottomElevation();
		// Get all components that are connected with the space with the relation
		// Nearest_Spaces
		Relation nearestSpacesRelation = Relation.of(Relation.Type.NEAREST_SPACES, Relation.Direction.BACKWARD);
		Collection<Component> nearestComponentsCollection = spaceComponent.getRelated(nearestSpacesRelation);

		// for all coverings
		for (Component boundaryComponent : nearestComponentsCollection) {
			if (boundaryComponent instanceof Covering) {
				// cast the component into a covering
				Covering targetCovering = (Covering) boundaryComponent;
				// get the type of the covering
				Covering.Type typeOfCovering = targetCovering.getType();
				String typeOfCoveringString = String.valueOf(typeOfCovering);

				// check whether the covering is from type "FLOORING"
				if (typeOfCoveringString.equals("FLOORING")) {
					// if so, get it's footprint
					Polygon2d coveringFootprint = targetCovering.getFootprint().getArea().getLargestPolygon();
					// check whether the point is inside the polygon and whether the flooring is not
					// above the space
					if (coveringFootprint.contains(point)
							&& targetCovering.getGlobalTopElevation() < spaceComponent.getGlobalTopElevation()) {
						// if so, get the covering's top elevation as elevation of the node
						topElevation = targetCovering.getGlobalTopElevation();
						bottomElevation = targetCovering.getGlobalBottomElevation();
					}
				}
			}
		}
		// return either the top elevation or the bottom elevation
		if (output.equals("top")) {
			return topElevation;
		} else {
			return bottomElevation;
		}
	}
					
	//************************************************************************************	
	//createCylinderTriangleMesh() creates a triangleMesh in form of a cylinder placed at the given circleCenter with the given diameter
	//the z-Position is defined by the bottom and top elevation
	//The number of vertices is defined by the circlePrecision.
	//A precision of 360 creates vertices in 1 degree steps.
	private TriangleMesh createCylinderTriangleMesh(MVector2d circleCenter, double circleDiameter, double circlePrecision, double bottomElevation, double topElevation) {
		//calculate the vertices of the bottom and top circle of the cylinder
		List<Vector3d> bottomVertices = createCircle(circleCenter, circleDiameter, circlePrecision, bottomElevation);
		List<Vector3d> topVertices = createCircle(circleCenter, circleDiameter, circlePrecision, topElevation);
		
		List<List<Vector3d>> polygonVerticeLists = new ArrayList<>();
		
		//add vertices of the bottom and the top polygon to the overall list
		polygonVerticeLists.add(bottomVertices);
		polygonVerticeLists.add(topVertices);
		
		//add the vertices of the side polygons
		for(int i = 0; i < circlePrecision; i++) {
			List<Vector3d> polygonVertices = new ArrayList<>();
			if(i != circlePrecision - 1) {
				polygonVertices.add(bottomVertices.get(i));
				polygonVertices.add(bottomVertices.get(i+1));
				polygonVertices.add(topVertices.get(i+1));
				polygonVertices.add(topVertices.get(i));
			} 
			else {
				polygonVertices.add(bottomVertices.get(i));
				polygonVertices.add(bottomVertices.get(0));
				polygonVertices.add(topVertices.get(0));
				polygonVertices.add(topVertices.get(i));
			}
			polygonVerticeLists.add(polygonVertices);
		}
		
		//create the polygons
		List<Polygon3d> polygons = new ArrayList<>();
		for(List<Vector3d> polygonVertices : polygonVerticeLists) {
			polygons.add(Polygon3d.create(polygonVertices));
		}
		
		TriangleMesh mesh = TriangleMesh.fromPolygons(polygons);
		
		return mesh;
	}
	
	//************************************************************************************
	//createCircle() creates a circle with the given center and diameter.
	//The circle is represented by vertices placed at the boundary of the circle.
	//The number of vertices is defined by the circlePrecision.
	//A precision of 360 creates vertices in 1 degree steps.
	//The method returns a list of the created vertices.
	private List<Vector3d> createCircle (Vector2d circleCenter, double circleDiameter, double circlePrecision, double zCoordinate) {
		
		// List for the vertices (Eckpunkte)
		List<Vector3d> vertices = new ArrayList<Vector3d>();
		
		// Creating the vertices of the circle		
		for(int i = 0; i < circlePrecision; i++) {
			double xCoordinate = circleCenter.getX() + Math.cos(i*Math.PI/(circlePrecision/2))*(circleDiameter/2);
			double yCoordinate = circleCenter.getY() + Math.sin(i*Math.PI/(circlePrecision/2))*(circleDiameter/2);
			Vector3d vertex = Vector3d.create(xCoordinate, yCoordinate, zCoordinate);
			vertices.add(vertex);
		}
		return vertices;
	}

	//************************************************************************************
	//createCuboidTriangleMesh() creates a triangleMesh in form of a cuboid placed at the given rectangleCenter with the given rectangleSides
	//the z-Position is defined by the bottom and top elevation
	//directionB is the direction of the rectangleSideB
	private TriangleMesh createCuboidTriangleMesh(MVector2d rectangleCenter, MVector2d directionB, double rectangleSideA, double rectangleSideB, double bottomElevation, double topElevation) {
		//calculate the vertices of the bottom and top rectangle of the cuboid
		List<Vector3d> bottomVertices = createRectangle(rectangleCenter, directionB, rectangleSideA, rectangleSideB, bottomElevation);
		List<Vector3d> topVertices = createRectangle(rectangleCenter, directionB, rectangleSideA, rectangleSideB, topElevation);

		// store the vertices of each surface in a list
		// bottom surface
		ArrayList<Vector3d> verticeList1 = new ArrayList<>();
		verticeList1.add(bottomVertices.get(0));
		verticeList1.add(bottomVertices.get(1));
		verticeList1.add(bottomVertices.get(2));
		verticeList1.add(bottomVertices.get(3));
		
		// top surface
		ArrayList<Vector3d> verticeList6 = new ArrayList<>();
		verticeList6.add(topVertices.get(0));
		verticeList6.add(topVertices.get(1));
		verticeList6.add(topVertices.get(2));
		verticeList6.add(topVertices.get(3));

		//side surfaces
		ArrayList<Vector3d> verticeList2 = new ArrayList<>();
		verticeList2.add(bottomVertices.get(0));
		verticeList2.add(bottomVertices.get(1));
		verticeList2.add(topVertices.get(1));
		verticeList2.add(topVertices.get(0));

		ArrayList<Vector3d> verticeList3 = new ArrayList<>();
		verticeList3.add(bottomVertices.get(1));
		verticeList3.add(bottomVertices.get(2));
		verticeList3.add(topVertices.get(2));
		verticeList3.add(topVertices.get(1));

		ArrayList<Vector3d> verticeList4 = new ArrayList<>();
		verticeList4.add(bottomVertices.get(2));
		verticeList4.add(bottomVertices.get(3));
		verticeList4.add(topVertices.get(3));
		verticeList4.add(topVertices.get(2));

		ArrayList<Vector3d> verticeList5 = new ArrayList<>();
		verticeList5.add(bottomVertices.get(3));
		verticeList5.add(bottomVertices.get(0));
		verticeList5.add(topVertices.get(0));
		verticeList5.add(topVertices.get(3));

		// combine the vertices to polygons which represent surfaces
		Polygon3d polygon1 = Polygon3d.create(verticeList1);
		Polygon3d polygon2 = Polygon3d.create(verticeList2);
		Polygon3d polygon3 = Polygon3d.create(verticeList3);
		Polygon3d polygon4 = Polygon3d.create(verticeList4);
		Polygon3d polygon5 = Polygon3d.create(verticeList5);
		Polygon3d polygon6 = Polygon3d.create(verticeList6);

		// create a list for all polygons
		ArrayList<Polygon3d> polygonList = new ArrayList<>();
		polygonList.add(polygon1);
		polygonList.add(polygon2);
		polygonList.add(polygon3);
		polygonList.add(polygon4);
		polygonList.add(polygon5);
		polygonList.add(polygon6);

		// create the triangle mesh from the polygons
		TriangleMesh mesh = TriangleMesh.fromPolygons(polygonList);

		return mesh;
	}
	
	//************************************************************************************
	//createRectangle() creates a rectangle with the given center and rectangle sides.
	//directionB is the direction of the rectangleSideB
	//The rectangle is represented by 4 vertices.
	//The method returns a list with this vectors
	private List<Vector3d> createRectangle (MVector2d rectangleCenter, MVector2d directionB, double rectangleSideA, double rectangleSideB, double elevation) {
		
		// List for the vertices (Eckpunkte)
		List<Vector3d> vertices = new ArrayList<Vector3d>();
		
		// Creating the vertices of the rectangle
		Vector2d point1 = rectangleCenter.subtract(directionB.scale(rectangleSideB/2)).add(rotateVector(directionB, Math.PI*3/2).scale(rectangleSideA/2));
		Vector2d point2 = point1.add(rotateVector(directionB, 0).scale(rectangleSideB));
		Vector2d point3 = point2.add(rotateVector(directionB, Math.PI/2).scale(rectangleSideA));
		Vector2d point4 = point3.add(rotateVector(directionB, Math.PI).scale(rectangleSideB));
		vertices.add(Vector3d.create(point1.getX(), point1.getY(), elevation));
		vertices.add(Vector3d.create(point2.getX(), point2.getY(), elevation));
		vertices.add(Vector3d.create(point3.getX(), point3.getY(), elevation));
		vertices.add(Vector3d.create(point4.getX(), point4.getY(), elevation));
		
		return vertices;
	}
	
	//************************************************************************************
	//createBoundingBox returns an AABB3d around the middlePoint with the given bottom and top elevation.
	//The boundingBox is a cuboid with 4 vertices at the bottom and 4 at the top.
	//The vertices are created with polar coordinates from the middle point. The diameter is given as parameter.
	//The vertices are created at 0, 90, 180 and 270 degrees
	private AABB3d createBoundingBox (Vector2d middlePoint, double bottomElevation, double topElevation, double diameter) {
		
		// List where the vertices are stored
		List<Vector3d> bbVertices = new ArrayList<Vector3d>();
		
		bbVertices.addAll(createCircle(middlePoint, diameter, 4., bottomElevation));
		bbVertices.addAll(createCircle(middlePoint, diameter, 4., topElevation));
		
		// Creating a boundingBox with the given edges
		AABB3d boundingBox = AABB3d.create(bbVertices);
		
		return boundingBox;
	}
		
	//************************************************************************************
	//clashCheck() determines whether the given movement area intersects the target component.
	//The method returns a list of results. If no intersections are found this list is empty
	private Collection<Result> clashCheck (Component door, Component targetComponent, double floorElevation, TriangleMesh movementAreaMesh, ResultFactory resultFactory, ResultCategory resultCategory) {
		Collection<Result> results = new ArrayList<>();
				
		// if-condition for the height of the target & the door component
		if((targetComponent.getGlobalBottomElevation() < door.getGlobalTopElevation()) && (targetComponent.getGlobalTopElevation() > floorElevation)) {

			// retrieve the TriangleMesh of the targetComponent
			TriangleMesh targetMesh = targetComponent.getTriangleMesh();
										
			// Intersection between the movementAreaMesh and the targetMesh and the targetArea
			TriangleMesh intersectionMesh = movementAreaMesh.intersection(targetMesh);
			Mesh visualMovementArea = Mesh.create(movementAreaMesh.difference(intersectionMesh).toTriangleCollection());
			Mesh visualIntersection = Mesh.create(ARGBColor.create(255, 0, 0, 255), intersectionMesh.toTriangleCollection());
			
			// if there is no intersection >> continue with the loop
			// if there is a intersection (tolerance 1cm^3; without tolerance there are bugs) >> create a result
			if(intersectionMesh.getVolume() > 0.000001) {
				String name = door.getName() + resources.getString("RE.ClashResult.NAME") + targetComponent.getName();
				String description = door.getName() + resources.getString("RE.ClashResult.NAME") + targetComponent.getName();
				Result result = resultFactory
					.create(name, description)
					.withInvolvedComponent(targetComponent) // adds the component in the dropdown menu of the result
					.withVisualization(visualization -> {
						visualization.addVisualizationItem(visualMovementArea);
						visualization.addVisualizationItem(visualIntersection);
					})
					.withSeverity(Severity.MODERATE)	//severity of the result
					.withCategory(resultCategory);		//assign result to ResultCategory;
			results.add(result);	
			}
		}
		return results;
	}
	
	//************************************************************************************
	//UI
	@Override
	public UIContainer getParametersUIDefinition() {
		// Vertical container with title
		UIContainer mainContainer =  UIContainerVertical.create(resources.getString("UI.EnoughSpaceRule.TITLE"),BorderType.LINE);
		// Description vertical container
		mainContainer.addComponent(UILabel.create(resources.getString("UI.EnoughSpaceRule.DESCRIPTION")));
		
		// Door filter
		mainContainer.addComponent(UIRuleParameter.create(rpComponentFilter));
		// Irrelevant spacess filter
		mainContainer.addComponent(UIRuleParameter.create(rpComponentFilterIrrelevantSpaces));
		// Obstacle filter
		mainContainer.addComponent(UIRuleParameter.create(rpComponentFilterObstacles));
		// self-defined container
		mainContainer.addComponent(movementArea());
				
		return mainContainer;
	}
	
	//Container for the movement area
	private UIComponent movementArea() {
		UIContainer uiContainer = UIContainerVertical.create(resources.getString("UI.MovementArea.TITLE"), BorderType.LINE);
		uiContainer.addComponent(UILabel.create(resources.getString("UI.MovementArea.DESCRIPTION")));
		
		UIContainer uiContainer0 = UIContainerVertical.create(resources.getString("rpChooseMovementAreaObject.DESCRIPTION"), BorderType.LINE);
		uiContainer0.addComponent(UIRadioButtonPanelHorizontal.create(rpEnumerationMovementArea));
		UIContainer uiContainer1 = UIContainerHorizontal.create();
		uiContainer1.addComponent(uiCircleContainer());
		uiContainer1.addComponent(uiRectangleContainer());
		uiContainer0.addComponent(uiContainer1);
		uiContainer.addComponent(uiContainer0);
		
		uiContainer.addComponent(UIRuleParameter.create(rpAreaOffset));
		
		UIContainer uiContainer2 = UIContainerVertical.create(resources.getString("rpChooseObjectHeight.DESCRIPTION"), BorderType.LINE);
		uiContainer2.addComponent(UIRadioButtonPanelVertical.create(rpEnumerationObjectHeight));
		uiContainer2.addComponent(UIRuleParameter.create(rpObjectHeight));
		uiContainer.addComponent(uiContainer2);
		
		uiContainer.addComponent(UIImage.create(resources.getImageUrl(resources.getString("UI.AreaOptionsImage"))));
								
		return uiContainer;
	}
	
	//Container for the circle option
	private UIContainer uiCircleContainer() {
		UIContainer uiContainer = UIContainerVertical.create();
		uiContainer.addComponent(UIRuleParameter.create(rpCircleDiameter));
		
		return uiContainer;
	}
	
	//Container for the rectangle option
		private UIContainer uiRectangleContainer() {
			UIContainer uiContainer = UIContainerVertical.create();
			uiContainer.addComponent(UIRuleParameter.create(rpRectangleSideA));
			uiContainer.addComponent(UIRuleParameter.create(rpRectangleSideB));
							
			return uiContainer;
		}

}

