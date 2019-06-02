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
import sys

from multiprocessing import Process, Queue
import socket


from rdflib import Namespace, Graph, logger, RDF, XSD, Literal
from flask import Flask, request

from PracticaTienda.utils.ACLMessages import get_message_properties, build_message, register_agent
from PracticaTienda.utils.FlaskServer import shutdown_server
from PracticaTienda.utils.Agent import Agent
from PracticaTienda.utils.OntoNamespaces import ACL
from PracticaTienda.utils.OntologyNamespaces import ECSDI

__author__ = 'Amazon V2'

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
    port = 9420
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


agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
messages_cnt = 0

# Datos del Agente

AgenteValoraciones = Agent('AgenteValorador',
                       agn.AgenteValorador,
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

    gr = register_agent(AgenteValoraciones, DirectoryAgent, AgenteValoraciones.uri, get_count())
    return gr


@app.route("/comm")
def comunicacion():
    global dsgraph
    global mss_cnt
    gr =  None
    logger.info ('Peticion de recomendacion recibida')

    # Extraemos el mensaje que nos envian
    mensaje = request.args['content']
    gm = Graph()
    gm.parse(data=mensaje)

    msgdic = get_message_properties(gm)

    #Comprobacion del mensaje

    if msgdic is None:
        gr = build_message(Graph(), ACL['no_entendido'],sender=AgenteValoraciones.uri, msgcnt=get_count())
    else:
        performative = msgdic['performative']

        if performative != ACL.request:
            gr = build_message(Graph(), ACL['no_entendido'], sender=AgenteValoraciones.uri, msgcnt=get_count())

        else:
            content = msgdic['content']
            accion = gm.value(subject=content, predicate=RDF.type)

            if accion == ECSDI.Peticion_Valorados:
                get_all_sells()
                if compras.__len__() == 0:
                    g = Graph()
                    serialize = g.serialize(format='xml')
                    return serialize, 200
                gr = findValProducts()
                logger.info('Respondemos a la peticion')
                serialize = gr.serialize(format='xml')
                return serialize, 200
            elif accion == ECSDI.Peticion_valorar:
                for item in gm.subjects(RDF.type, ACL.FipaAclMessage):
                    gm.remove((item, None, None))
                for item in gm.subjects(RDF.type, ECSDI.Peticion_valorar):
                    gm.remove((item, None, None))
                guardarValoraciones(gm)
                serialize = gm.serialize(format='xml')
                return serialize, 200


def guardarValoraciones(gm):
    ontologyFile = open('../Datos/Valoraciones')
    graph = Graph()
    graph.parse(ontologyFile, format='turtle')
    graph += gm
    graph.serialize(destination='../Datos/Valoraciones', format="turtle")
    pass

def findValProducts():
    graph = Graph()
    ontologyFile = open('../Datos/productos')
    graph.parse(ontologyFile, format='turtle')

    query = """
        prefix rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        prefix xsd:<http://www.w3.org/2001/XMLSchema#>
        prefix default:<http://www.owl-ontologies.com/ECSDIAmazon.owl#>
        prefix owl:<http://www.w3.org/2002/07/owl#>
        SELECT ?producto ?nombre ?marca ?modelo ?precio ?peso
        where {
            { ?producto rdf:type default:Producto } UNION { ?producto rdf:type default:Producto_externo } .
            ?producto default:Nombre ?nombre .
            ?producto default:Marca ?marca .
            ?producto default:Modelo ?modelo .
            ?producto default:Precio ?precio .
            ?producto default:Peso ?peso .
            FILTER("""

    bol = 0
    for row in compras:
        for item in row[1]:
            if bol == 1:
                query += """ || """
            query += """str(?nombre) = '""" + item + """'"""
            bol = 1
    query += """)}"""


    graph_query = graph.query(query)
    result = Graph()
    result.bind('ECSDI', ECSDI)
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
        result.add((subject, RDF.type, ECSDI.Producte))
        result.add((subject, ECSDI.Marca, Literal(marca, datatype=XSD.string)))
        result.add((subject, ECSDI.Modelo, Literal(modelo, datatype=XSD.string)))
        result.add((subject, ECSDI.Precio, Literal(precio, datatype=XSD.float)))
        result.add((subject, ECSDI.Peso, Literal(peso, datatype=XSD.float)))
        result.add((subject, ECSDI.Nombre, Literal(nombre, datatype=XSD.string)))
    return result


def get_all_sells():
    # [0] = url / [1] = [{producte}] / [2] = precio_total
    global compras
    compras = []
    graph_compres = Graph()
    graph_compres.parse(open('../Datos/Compras'), format='turtle')

    for compraUrl in graph_compres.subjects(RDF.type, ECSDI.Compra):
        single_sell = [compraUrl]
        products = []
        for productUrl in graph_compres.objects(subject=compraUrl, predicate=ECSDI.Productos):
            products.append(graph_compres.value(subject=productUrl, predicate=ECSDI.Nombre))
        single_sell.append(products)
        compras.append(single_sell)

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
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')

