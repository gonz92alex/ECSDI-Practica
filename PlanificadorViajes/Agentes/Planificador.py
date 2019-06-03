# -*- coding: utf-8 -*-
"""
Created on Fri Dec 27 15:58:13 2013

Esqueleto de agente usando los servicios web de Flask

/comm es la entrada para la recepcion de mensajes del agente
/Stop es la entrada que para el agente

Tiene una funcion AgentBehavior1 que se lanza como un thread concurrente

Asume que el agente de registro esta en el puerto 9000

@author: javier
"""

from __future__ import print_function

import argparse

from multiprocessing import Process, Queue
import socket


from rdflib import Namespace, Graph, logger, RDF, XSD, Literal
from flask import Flask, request

from PlanificadorViajes.AgentUtil.ACLMessages import register_agent, build_message, get_message_properties
from PlanificadorViajes.AgentUtil.FlaskServer import shutdown_server
from PlanificadorViajes.AgentUtil.Agent import Agent
from PlanificadorViajes.AgentUtil.OntologyNamespaces import ACL
from PlanificadorViajes.AgentUtil.OntologyNamespaces import Ontologia

__author__ = 'ecsdi'

parser = argparse.ArgumentParser()
parser.add_argument('--open', help="Define si el servidor est abierto al exterior o no", action='store_true',
                    default=False)
parser.add_argument('--port', type=int, help="Puerto de comunicacion del agente")
parser.add_argument('--dhost', default=socket.gethostname(), help="Host del agente de directorio")
parser.add_argument('--dport', type=int, help="Puerto de comunicacion del agente de directorio")
parser.add_argument('--host', default=socket.gethostname(), help="Host del agente")

args = parser.parse_args()

# Configuration stuff
if args.port is None:
    port = 9081
else:
    port = args.port

if args.open is None:
    hostname = '0.0.0.0'
else:
    hostname = args.host

if args.dport is None:
    dport = 9000
else:
    dport = args.dport

if args.dhost is None:
    dhostname = socket.gethostname()
else:
    dhostname = args.dhost


agn = Namespace("http://www.agentes.org/#")

# Contador de mensajes
messages_cnt = 0

# Datos del Agente

AgentePlanificador = Agent('Planificador',
                       agn.AgentePlanificador,
                       'http://%s:%d/comm' % (hostname, port),
                       'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:%d/Register' % (dhostname, dport),
                       'http://%s:%d/Stop' % (dhostname, dport))


# Global triplestore graph
dsgraph = Graph()

cola1 = Queue()

# Flask stuff
app = Flask(__name__, template_folder='../templates')

def get_count():
    global messages_cnt
    messages_cnt += 1
    return messages_cnt

def register_message():
    """
    Envia un mensaje de registro al servicio de registro
    usando una performativa Request y una accion Register del
    servicio de directorio
    :param gmess:
    :return:
    """

    logger.info('Nos registramos')

    gr = register_agent(AgentePlanificador, DirectoryAgent, AgentePlanificador.uri, get_count())
    return gr


@app.route("/comm")
def comunicacion():
    global dsgraph
    global mss_cnt
    gr =  None
    logger.info('Peticion de info recibida')

    # Extraemos el mensaje que nos envian
    mensaje = request.args['content']
    gm = Graph()
    gm.parse(data=mensaje)

    msgdic = get_message_properties(gm)

    #Comprobacion del mensaje

    if msgdic is None:
        gr = build_message(Graph(), ACL['no_entendido'],sender=AgentePlanificador.uri, msgcnt=get_count())
    else:
        performative = msgdic['performative']

        if performative != ACL.request:
            gr = build_message(Graph(), ACL['no_entendido'], sender=AgentePlanificador.uri, msgcnt=get_count())

        else:

            content = msgdic['content']
            accion = gm.value(subject=content, predicate=RDF.type)

            if accion == Ontologia.Peticion_Buscar:
                logger.info('Agente Planificador recibe una peticion de búsqueda, la tratamos')
                restricciones = gm.objects(content, Ontologia.Restricciones)
                restricciones_vec = {}
                for restriccion in restricciones:
                    if gm.value(subject=restriccion, predicate=RDF.type) == Ontologia.Restriccion_Marca:
                        marca = gm.value(subject=restriccion, predicate=Ontologia.Marca)
                        logger.info('MARCA: ' + marca)
                        restricciones_vec['brand'] = marca
                    elif gm.value(subject=restriccion, predicate=RDF.type) == Ontologia.Restriccion_modelo:
                        modelo = gm.value(subject=restriccion, predicate=Ontologia.Modelo)
                        logger. info('MODELO: ' + modelo)
                        restricciones_vec['modelo'] = modelo
                    elif gm.value(subject=restriccion, predicate=RDF.type) == Ontologia.Rango_precio:
                        preu_max = gm.value(subject=restriccion, predicate=Ontologia.Precio_max)
                        preu_min = gm.value(subject=restriccion, predicate=Ontologia.Precio_min)
                        if preu_min:
                            logger.info('Preu minim: ' + preu_min)
                            restricciones_vec['min_price'] = preu_min.toPython()
                        if preu_max:
                            logger.info('Preu maxim: ' + preu_max)
                            restricciones_vec['max_price'] = preu_max.toPython()

                gr = findProducts(**restricciones_vec)

                logger.info('Respondemos a la peticion')

                serialize = gr.serialize(format='xml')
                return serialize, 200


def findFlights(origin=None, destination=None):
    graph = Graph()
    ontologyFile = open('../Datos/productos')
    graph.parse(ontologyFile, format='turtle')

    first = second = 0
    query = """
        prefix rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        prefix xsd:<http://www.w3.org/2001/XMLSchema#>
        prefix default:<http://www.owl-ontologies.com/ECSDIAmazon.owl#>
        prefix owl:<http://www.w3.org/2002/07/owl#>
        SELECT DISTINCT ?producto ?nombre ?marca ?modelo ?precio ?peso
        where {
            { ?producto rdf:type default:Producto } UNION { ?producto rdf:type default:Producto_externo } .
            ?producto default:Nombre ?nombre .
            ?producto default:Marca ?marca .
            ?producto default:Modelo ?modelo .
            ?producto default:Precio ?precio .
            ?producto default:Peso ?peso .
            FILTER("""

    if modelo is not None:
        query += """str(?modelo) = '""" + modelo + """'"""
        first = 1

    if brand is not None:
        if first == 1:
            query += """ && """
        query += """str(?marca) = '""" + brand + """'"""
        second = 1

    if first == 1 or second == 1:
        query += """ && """
    query += """?precio >= """ + str(min_price) + """ &&
                ?precio <= """ + str(max_price) + """  )}
                order by asc(UCASE(str(?nombre)))"""

    graph_query = graph.query(query)
    result = Graph()
    result.bind('ECSDI', Ontologia)
    product_count = 0
    for row in graph_query:
        nombre = row.nombre
        modelo = row.modelo
        marca = row.marca
        precio = row.precio
        peso = row.peso
        logger.debug(nombre, marca, modelo, precio)
        subject = row.producto
        product_count += 1
        result.add((subject, RDF.type, Ontologia.Producte))
        result.add((subject, Ontologia.Marca, Literal(marca, datatype=XSD.string)))
        result.add((subject, Ontologia.Modelo, Literal(modelo, datatype=XSD.string)))
        result.add((subject, Ontologia.Precio, Literal(precio, datatype=XSD.float)))
        result.add((subject, Ontologia.Peso, Literal(peso, datatype=XSD.float)))
        result.add((subject, Ontologia.Nombre, Literal(nombre, datatype=XSD.string)))
    return result





@app.route("/Stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"


def tidyup():
    """
    Acciones previas a parar el agente
    Guardar el grafo en un archivo
    """
    pass


def agentbehavior1():

    gr = register_message()

    pass



if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=())
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port, debug=True)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')

def buscar(origen, destino):
    amadeus = Client(
        client_id='s2h4iHhivYGEkIyyVuzNAUxL7SHxVpSl',
        client_secret='sUSz5eLygipHqv1C'
    )
    date = dateToApi(request.args.get('date', None))
    print(origen)
    print(destino)
    print(date)
    #return 'Quieres ir de '+origen+' a '+destino
    try:
        res = amadeus.shopping.flight_dates.get(
            origin=origen,
            destination=destino
        )
        return jsonify(res.result)
    except ResponseError as error:
        print('en error')
        return jsonify(error.response.result)
